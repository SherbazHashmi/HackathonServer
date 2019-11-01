from fastai.vision import ImageSegment, Image
from fastai.vision.image import open_image, show_image, pil2tensor
from fastai.vision.data import SegmentationProcessor, ImageItemList
from fastai.layers import CrossEntropyFlat
from fastai.basic_train import LearnerCallback
import torch
import warnings
import PIL
import numpy as np

class ArcGISImageSegment(Image):
    "Support applying transforms to segmentation masks data in `px`."
    def __init__(self, x, cmap=None, norm=None):
        super(ArcGISImageSegment, self).__init__(x)
        self.cmap = cmap
        self.mplnorm = norm

    def lighting(self, func, *args, **kwargs):
        return self

    def refresh(self):
        self.sample_kwargs['mode'] = 'nearest'
        return super().refresh()

    @property
    def data(self):
        "Return this image pixels as a `LongTensor`."
        return self.px.long()

    def show(self, ax=None, figsize:tuple=(3,3), title=None, hide_axis:bool=True,
        cmap='tab20', alpha:float=0.5, **kwargs):
        "Show the `ImageSegment` on `ax`."
        ax = show_image(self, ax=ax, hide_axis=hide_axis, cmap=self.cmap, figsize=figsize,
                        interpolation='nearest', alpha=alpha, vmin=0, norm=self.mplnorm, **kwargs)
        if title: ax.set_title(title)

def is_no_color(color_mapping):
    if isinstance(color_mapping, dict):
        color_mapping = list(color_mapping.values())
    return (np.array(color_mapping) == [-1., -1., -1.]).any()

class ArcGISSegmentationLabelList(ImageItemList):
    "`ItemList` for segmentation masks."
    _processor = SegmentationProcessor
    def __init__(self, items, classes=None, class_mapping=None, color_mapping=None, **kwargs):
        super().__init__(items, **kwargs)
        self.class_mapping = class_mapping
        self.color_mapping = color_mapping
        self.copy_new.append('classes')
        self.classes, self.loss_func = classes, CrossEntropyFlat(axis=1)

        if is_no_color(list(color_mapping.values())):
            self.cmap = 'tab20'  ## compute cmap from palette
            import matplotlib as mpl
            bounds = list(color_mapping.keys())
            if len(bounds) < 3: # Two handle two classes i am adding one number to the classes which is not already in bounds
                bounds = bounds + [max(bounds)+1]
            self.mplnorm = mpl.colors.BoundaryNorm(bounds, len(bounds))
        else:
            import matplotlib as mpl
            bounds = list(color_mapping.keys())
            if len(bounds) < 3: # Two handle two classes i am adding one number to the classes which is not already in bounds
                bounds = bounds + [max(bounds)+1]
            self.cmap = mpl.colors.ListedColormap(np.array(list(color_mapping.values()))/255)
            self.mplnorm = mpl.colors.BoundaryNorm(bounds, self.cmap.N)

        if len(color_mapping.keys()) == 1:
            self.cmap = 'tab20'
            self.mplnorm = None
        

    def open(self, fn):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning) # EXIF warning from TiffPlugin
            x = PIL.Image.open(fn)
            if x.palette is not None:
                x = x.convert('P')
            else:
                x = x.convert('L')
            x = pil2tensor(x, np.float32)

        return ArcGISImageSegment(x, cmap=self.cmap, norm=self.mplnorm)

    def analyze_pred(self, pred, thresh:float=0.5): 
        label_mapping = {(idx + 1):value for idx, value in enumerate(self.class_mapping.keys())}
        out = pred.argmax(dim=0)[None]
        predictions = torch.zeros_like(out)
        for key, value in label_mapping.items():
            predictions[out==key] = value
        return predictions

    def reconstruct(self, t): 
        return ArcGISImageSegment(t, cmap=self.cmap, norm=self.mplnorm)

class ArcGISSegmentationItemList(ImageItemList):
    "`ItemList` suitable for segmentation tasks."
    _label_cls, _square_show_res = ArcGISSegmentationLabelList, False

class LabelCallback(LearnerCallback):
    def __init__(self, learn):
        super().__init__(learn)
        import pdb
        self.label_mapping = {value:(idx+1) for idx, value in enumerate(learn.data.class_mapping.keys())}
        
    def on_batch_begin(self, last_input, last_target, **kwargs):
        modified_target = torch.zeros_like(last_target)
        for label, idx in self.label_mapping.items():
            modified_target[last_target==label] = idx
        return last_input, modified_target