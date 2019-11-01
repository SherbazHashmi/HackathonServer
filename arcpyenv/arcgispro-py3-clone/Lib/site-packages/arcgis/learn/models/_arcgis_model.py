try:
    from fastai.callbacks import TrackerCallback, EarlyStoppingCallback
except ImportError:
    class TrackerCallback():
        pass
import arcgis
from pathlib import Path
import os
import tempfile

class SaveModelCallback(TrackerCallback):

    def __init__(self, model, every='improvement', name='bestmodel', load_best_at_end=True, **kwargs):
        super().__init__(learn=model.learn, **kwargs)
        self.model = model
        self.every = every
        self.name = name        
        self.load_best_at_end = load_best_at_end
        if self.every not in ['improvement', 'epoch']:
            warn('SaveModel every {} is invalid, falling back to "improvement".'.format(self.every))
            self.every = 'improvement'

    def on_epoch_end(self, epoch, **kwargs):
        "Compare the value monitored to its best score and maybe save the model."
        if self.every=="epoch": self.model.save('{}_{}'.format(self.name, epoch))
        else: #every="improvement"
            current = self.get_monitor_value()
            if current is not None and self.operator(current, self.best):
                if arcgis.env.verbose:
                    print('saving checkpoint.')
                self.best = current
                self.model._save('{}'.format(self.name), zip_files=False)

    def on_train_end(self, **kwargs):
        "Load the best model."      
        if self.every=="improvement" and self.load_best_at_end:
            self.model.load('{}'.format(self.name))
            self.model.save('{}'.format(self.name))

class ArcGISModel(object):
    
    def lr_find(self):
        """
        Runs the Learning Rate Finder, and displays the graph of it's output.
        Helps in choosing the optimum learning rate for training the model.
        """
        from IPython.display import clear_output
        self.learn.lr_find()
        clear_output()
        self.learn.recorder.plot()
    
    
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
        if early_stopping:
            callbacks.append(EarlyStoppingCallback(learn=self.learn, monitor='val_loss', min_delta=0.01, patience=5))
        if checkpoint:
            callbacks.append(SaveModelCallback(self, monitor='val_loss', every='improvement', name='checkpoint'))

        if one_cycle:
            self.learn.fit_one_cycle(epochs, lr, callbacks=callbacks, **kwargs)
        else:
            self.learn.fit(epochs, lr, callbacks=callbacks, **kwargs)
        
    def unfreeze(self):
        """
        Unfreezes the earlier layers of the model for fine-tuning.
        """
        self.learn.unfreeze()
        
    def _save(self, name_or_path, zip_files=True):
        temp = self.learn.path

        if '\\' in name_or_path or '/' in name_or_path:
            path = Path(name_or_path)
            name = path.parts[-1]
            # to make fastai save to both path and with name    
            self.learn.path = path
            self.learn.model_dir = ''
            if not os.path.exists(self.learn.path):
                os.makedirs(self.learn.path)
        else:
            # fixing fastai bug
            self.learn.path = self.learn.path.parent
            self.learn.model_dir =  Path(self.learn.model_dir) /  name_or_path
            if not os.path.exists(self.learn.path / self.learn.model_dir):
                os.makedirs(self.learn.path / self.learn.model_dir)
            name = name_or_path

        try:
            saved_path = self.learn.save(name,  return_path=True)
            # undoing changes to self.learn.path
        except Exception as e:  
            raise e
        finally:
            self.learn.path = temp
            self.learn.model_dir = 'models'

        zip_name = self._create_emd(saved_path)
        with open(saved_path.parent / self._emd_template['InferenceFunction'], 'w') as f:
            f.write(self._code)
        if zip_files:
            self._create_zip(zip_name, str(saved_path.parent))
        if arcgis.env.verbose:
            print('Created model files at {spp}'.format(spp=saved_path.parent))
        return saved_path.parent

    def save(self, name_or_path):
        """
        Saves the model weights, creates an Esri Model Definition and Deep
        Learning Package zip for deployment to Image Server or ArcGIS Pro
        Train the model for the specified number of epocs and using the
        specified learning rates.
        
        =====================   ===========================================
        **Argument**            **Description**
        ---------------------   -------------------------------------------
        name_or_path            Required string. Name of the model to save. It
                                stores it at the pre-defined location. If path
                                is passed then it stores at the specified path
                                with model name as directory name. and creates
                                all the intermediate directories.
        =====================   ===========================================
        """        
        return self._save(name_or_path)

        
    def _create_zip(self, zipname, path):
        import shutil

        temp_dir = tempfile.TemporaryDirectory().name
        zip_file = shutil.make_archive(os.path.join(temp_dir, zipname), 'zip', path)
        if os.path.exists(os.path.join(path, zipname) + '.zip'):
            os.remove(os.path.join(path, zipname) + '.zip')
        shutil.move(zip_file, path)
        
    def load(self, name_or_path):
        """
        Loads a saved model for inferencing or fine tuning from the specified
        path or model name.
        
        =====================   ===========================================
        **Argument**            **Description**
        ---------------------   -------------------------------------------
        name_or_path            Required string. Name of the model to load from
                                the pre-defined location. If path is passed then
                                it loads from the specified path with model name
                                as directory name. Path to ".pth" file can also
                                be passed
        =====================   ===========================================
        """
        temp = self.learn.path
        if '\\' in name_or_path or '/' in name_or_path:
            path = Path(name_or_path)
            # to make fastai from both path and with name
            if path.is_file():
                name = path.stem
                self.learn.path = path.parent
            else:
                name = path.parts[-1]
                self.learn.path = path
            self.learn.model_dir = ''
        else:
            # fixing fastai bug
            self.learn.path = self.learn.path.parent
            self.learn.model_dir =  Path(self.learn.model_dir) /  name_or_path
            name = name_or_path

        try:
            self.learn.load(name)
        except Exception as e:
            raise e
        finally:
            # undoing changes to self.learn.path
            self.learn.path = temp
            self.learn.model_dir = 'models'