import os, json, tempfile
from pathlib import Path
from ._codetemplate import image_classifier_prf
from ._ssd import _raise_fastai_import_error, _EmptyData
from functools import partial

try:
    from ._arcgis_model import ArcGISModel, SaveModelCallback
    import torch
    from torchvision import models
    from fastai.vision.learner import unet_learner
    import numpy as np
    from ._unet_utils import is_no_color, LabelCallback
    from fastai.callbacks import EarlyStoppingCallback
    HAS_FASTAI = True
except Exception as e:
    HAS_FASTAI = False

_CLASS_TEMPLATE =     {
      "Value" : 1,
      "Name" : "1",
      "Color" : []
    }

_EMD_TEMPLATE = {
    "Framework":"arcgis.learn.models._inferencing",
    "ModelConfiguration":"_unet",
    "ModelFile":"",
    "InferenceFunction": "ArcGISImageClassifier.py",
    "ExtractBands":[0,1,2],
    "ImageWidth":400,
    "ImageHeight":400,
    "Classes" : []
}

def accuracy(input, target, void_code=0, class_mapping=None):  
    target = target.squeeze(1) 
    mask = target != void_code
    return (input.argmax(dim=1)[mask] == target[mask]).float().mean()

class UnetClassifier(ArcGISModel):

    """
    Creates a Unet like classifier based on given pretrained encoder.

    =====================   ===========================================
    **Argument**            **Description**
    ---------------------   -------------------------------------------
    data                    Required fastai Databunch. Returned data object from
                            `prepare_data` function.
    ---------------------   -------------------------------------------
    backbone                Optional function. Backbone CNN model to be used for
                            creating the base of the `UnetClassifier`, which
                            is `resnet34` by default.
    ---------------------   -------------------------------------------
    pretrained_path         Optional string. Path where pre-trained model is
                            saved.
    =====================   ===========================================

    :returns: `UnetClassifier` Object
    """

    
    def __init__(self, data, backbone=None, pretrained_path=None):
      
        super().__init__()

        self._device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')

        if not HAS_FASTAI:
            _raise_fastai_import_error()

        self._emd_template = _EMD_TEMPLATE
        self._code = image_classifier_prf

        if backbone is None:
            self._backbone = models.resnet34
        elif type(backbone) is str:
            self._backbone = getattr(models, backbone)
        else:
            self._backbone = backbone

        acc_metric = partial(accuracy, void_code=0, class_mapping=data.class_mapping)
        self._data = data
        self.learn = unet_learner(data, arch=self._backbone, metrics=acc_metric, wd=1e-2, bottle=True, last_cross=True)
        self.learn.model = self.learn.model.to(self._device)

        if pretrained_path is not None:
            self.load(pretrained_path)
        
    @classmethod
    def from_emd(cls, data, emd_path):
        emd_path = Path(emd_path)
        with open(emd_path) as f:
            emd = json.load(f)
            
        model_file = Path(emd['ModelFile'])
        
        if not model_file.is_absolute():
            model_file = emd_path.parent / model_file
            
        model_params = emd['ModelParameters']

        try:
            class_mapping = {i['Value'] : i['Name'] for i in emd['Classes']}
            color_mapping = {i['Value'] : i['Color'] for i in emd['Classes']}
        except KeyError:
            class_mapping = {i['ClassValue'] : i['ClassName'] for i in emd['Classes']} 
            color_mapping = {i['ClassValue'] : i['Color'] for i in emd['Classes']}                

        
        if data is None:
            empty_data = _EmptyData(path=tempfile.TemporaryDirectory().name, loss_func=None, c=len(class_mapping) + 1, chip_size=emd['ImageHeight'])
            empty_data.class_mapping = class_mapping
            empty_data.color_mapping = color_mapping
            return cls(empty_data, **model_params, pretrained_path=str(model_file))
        else:
            return cls(data, **model_params, pretrained_path=str(model_file))        
        
        
    def _create_emd(self, path):
        import random
        _EMD_TEMPLATE['ModelFile'] = path.name
        _EMD_TEMPLATE['ImageHeight'] = self._data.chip_size
        _EMD_TEMPLATE['ImageWidth'] = self._data.chip_size
        _EMD_TEMPLATE['ModelParameters'] = {
                                            'backbone': self._backbone.__name__
                                           }
        _EMD_TEMPLATE['Classes'] = []
        for i, class_name in enumerate(self._data.classes[1:]): # 0th index is background
            inverse_class_mapping = {v: k for k, v in self._data.class_mapping.items()}
            _CLASS_TEMPLATE["Value"] = inverse_class_mapping[class_name]
            _CLASS_TEMPLATE["Name"] = class_name
            color = [random.choice(range(256)) for i in range(3)] if is_no_color(self._data.color_mapping) else self._data.color_mapping[inverse_class_mapping[class_name]]
            _CLASS_TEMPLATE["Color"] = color
            _EMD_TEMPLATE['Classes'].append(_CLASS_TEMPLATE.copy())
            
        json.dump(_EMD_TEMPLATE, open(path.with_suffix('.emd'), 'w'), indent=4)
        return path.stem

    def fit(self, epochs=10, lr=slice(1e-4,3e-3), one_cycle=True, early_stopping=False, checkpoint=True, **kwargs):
        """
        Train the model for the specified number of epocs and using the
        specified learning rates
        
        =====================   ===========================================
        **Argument**            **Description**
        ---------------------   -------------------------------------------
        epochs                  Required integer. Number of cycles of training
                                on the data. Increase it if underfitting.
        ---------------------   -------------------------------------------
        lr                      Required float or slice of floats. Learning rate
                                to be used for training the model. Select from
                                the `lr_find` plot.
        ---------------------   -------------------------------------------
        one_cycle               Optional boolean. Parameter to select 1cycle
                                learning rate schedule. If set to `False` no 
                                learning rate schedule is used.       
        ---------------------   -------------------------------------------
        early_stopping          Optional boolean. Parameter to add early stopping.
                                If set to `True` training will stop if validation
                                loss stops improving for 5 epochs.       
        ---------------------   -------------------------------------------
        checkpoint              Optional boolean. Parameter to save the best model
                                during training. If set to `True` the best model 
                                based on validation loss will be saved during 
                                training.
        =====================   ===========================================
        """
        callbacks = kwargs['callbacks'] if 'callbacks' in kwargs.keys() else []
        kwargs.pop('callbacks', None)
        callbacks.append(LabelCallback(self.learn))
        if early_stopping:
            callbacks.append(EarlyStoppingCallback(learn=self.learn, monitor='val_loss', min_delta=0.01, patience=5))
        if checkpoint:
            callbacks.append(SaveModelCallback(self, monitor='val_loss', every='improvement', name='checkpoint'))

        if one_cycle:
            self.learn.fit_one_cycle(epochs, lr, callbacks=callbacks, **kwargs)
        else:
            self.learn.fit(epochs, lr, callbacks=callbacks, **kwargs)

    def show_results(self, rows=5, **kwargs):
        """
        Displays the results of a trained model on a part of the validation set.
        """
        if rows > self._data.batch_size:
            rows = self._data.batch_size
        self.learn.show_results(rows=rows, **kwargs)             
