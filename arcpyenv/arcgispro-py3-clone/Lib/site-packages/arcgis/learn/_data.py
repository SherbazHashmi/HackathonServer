try:
    from fastai.vision.data import imagenet_stats, ImageItemList
    from fastai.vision.transform import crop, rotate, dihedral_affine, brightness, contrast, skew, rand_zoom, get_transforms
    import torch
    from pathlib import Path
    from functools import partial
    import xml.etree.ElementTree as ET
    from .models._ssd_utils import SSDObjectItemList
    from .models._unet_utils import ArcGISSegmentationItemList
    import math
    import sys
    import json
    import random
    from PIL import Image as pilImage
    import numpy as np
    import warnings
    HAS_FASTAI = True
except:
    HAS_FASTAI = False

def _raise_fastai_import_error():
    raise Exception('This module requires fastai, PyTorch and torchvision as its dependencies. Install it using "conda install -c pytorch -c fastai fastai=1.0.39 pytorch=1.0.0 torchvision"')

def _bb_pad_collate(samples, pad_idx=0):
    "Function that collect `samples` of labelled bboxes and adds padding with `pad_idx`."
    arr = []
    for s in samples:
        try:
            arr.append(len(s[1].data[1]))
        except Exception as e:
            # set_trace()
            # print(s[1].data[1],s[1].data[1],e)
            arr.append(0)
    max_len = max(arr)
#    max_len = max([len(s[1].data[1]) for s in samples])
    bboxes = torch.zeros(len(samples), max_len, 4)
    labels = torch.zeros(len(samples), max_len).long() + pad_idx
    imgs = []
    for i,s in enumerate(samples):
        imgs.append(s[0].data[None])
        bbs, lbls = s[1].data
        # print(bbs, lbls)
        try:
            bboxes[i,-len(lbls):] = bbs
            labels[i,-len(lbls):] = lbls
        except Exception as e:
            pass
    return torch.cat(imgs,0), (bboxes,labels)

def _get_bbox_lbls(imagefile, class_mapping):
    xmlfile = imagefile.parents[1] / 'labels' / imagefile.name.replace('{ims}'.format(ims=imagefile.suffix), '.xml')
    tree = ET.parse(xmlfile)
    xmlroot = tree.getroot()
    bboxes  = []
    classes = []
    for child in xmlroot:
        if child.tag == 'object':
            xmin, ymin, xmax, ymax = float(child[1][0].text),\
            float(child[1][1].text),\
            float(child[1][2].text),\
            float(child[1][3].text)
            bboxes.append([ymin, xmin, ymax, xmax])
            classes.append(class_mapping[int(child[0].text)])

    return [bboxes, classes]

def _get_lbls(imagefile, class_mapping):
    xmlfile = imagefile.parents[1] / 'labels' / imagefile.name.replace('{ims}'.format(ims=imagefile.suffix), '.xml')
    tree = ET.parse(xmlfile)
    xmlroot = tree.getroot()
    bboxes  = []
    classes = []
    for child in xmlroot:
        if child.tag == 'object':
            xmin, ymin, xmax, ymax = float(child[1][0].text),\
            float(child[1][1].text),\
            float(child[1][2].text),\
            float(child[1][3].text)
            bboxes.append([ymin, xmin, ymax, xmax])
            classes.append(class_mapping[int(child[0].text)])

    return classes[0]

def prepare_data(path, class_mapping=None, chip_size=224, val_split_pct=0.1, batch_size=64, transforms=None, collate_fn=_bb_pad_collate, seed=42, dataset_type = None):
    """
    Prepares a Fast.ai DataBunch from the exported Pascal VOC image chips
    exported by Export Training Data tool in ArcGIS Pro or Image Server.
    This DataBunch consists of training and validation DataLoaders with the
    specified transformations, chip size, batch size, split percentage.

    =====================   ===========================================
    **Argument**            **Description**
    ---------------------   -------------------------------------------
    path                    Required string. Path to data directory.
    ---------------------   -------------------------------------------
    class_mapping           Optional dictionary. Mapping from id to
                            its string label.
    ---------------------   -------------------------------------------
    chip_size               Optional integer. Size of the image to train the
                            model.
    ---------------------   -------------------------------------------
    val_split_pct           Optional float. Percentage of training data to keep
                            as validation.
    ---------------------   -------------------------------------------
    batch_size              Optional integer. Batch size for mini batch gradient
                            descent (Reduce it if getting CUDA Out of Memory
                            Errors).
    ---------------------   -------------------------------------------
    transforms              Optional tuple. Fast.ai transforms for data
                            augmentation of training and validation datasets
                            respectively (We have set good defaults which work
                            for satellite imagery well).
    ---------------------   -------------------------------------------
    collate_fn              Optional function. Passed to PyTorch to collate data
                            into batches(usually default works).
    ---------------------   -------------------------------------------
    seed                    Optional integer. Random seed for reproducible
                            train-validation split.
    ---------------------   -------------------------------------------
    dataset_type            Optional string. `prepare_data` function will infer 
                            the `dataset_type` on its own if it contains a 
                            map.txt file. If the path does not contain the 
                            map.txt file pass either of 'PASCAL_VOC_rectangles', 
                            'RCNN_Masks' and 'Classified_Tiles'                    
                            
    =====================   ===========================================

    :returns: fastai DataBunch object
    """

    if not HAS_FASTAI:
        _raise_fastai_import_error()

    if type(path) is str:
        path = Path(path)

    databunch_kwargs = {'num_workers':0} if sys.platform == 'win32' else {}

    json_file = path / 'esri_model_definition.emd'
    with open(json_file) as f:
        emd = json.load(f)

    if class_mapping is None:
        try:
            class_mapping = {i['Value'] : i['Name'] for i in emd['Classes']}
        except KeyError:
            class_mapping = {i['ClassValue'] : i['ClassName'] for i in emd['Classes']}
    
    color_mapping = None
    if color_mapping is None:
        try:
            color_mapping = {i['Value'] : i['Color'] for i in emd['Classes']}
        except KeyError:          
            color_mapping = {i['ClassValue'] : i['Color'] for i in emd['Classes']}                

        # if [-1, -1, -1] in color_mapping.values():
        #     for c_idx, c_color in color_mapping.items():
        #         if c_color[0] == -1:
        #             color_mapping[c_idx] = [random.choice(range(256)) for i in range(3)]

        #color_mapping[0] = [0, 0, 0] 

    if dataset_type is None:

        stats_file = path / 'esri_accumulated_stats.json'
        with open(stats_file) as f:
            stats = json.load(f)
            dataset_type = stats['MetaDataMode']

        # imagefile_types = ['png', 'jpg', 'tif', 'jpeg', 'tiff']
        # bboxfile_types = ['xml', 'json']
        with open(path / 'map.txt') as f:
            line = f.readline()
        # left = line.split()[0].split('.')[-1].lower()
        right = line.split()[1].split('.')[-1].lower()
        
        # if (left in imagefile_types) and (right in imagefile_types):
        #     dataset_type = 'RCNN_Masks'
        # elif (left in imagefile_types) and (right in bboxfile_types):
        #     dataset_type = 'PASCAL_VOC_rectangles'
        # else:
        #     raise NotImplementedError('Cannot infer dataset type. The dataset type is not implemented')            
        
    
    if dataset_type in ['RCNN_Masks', 'Classified_Tiles']:
        
        def get_y_func(x, ext=right):
            return x.parents[1] / 'labels' / (x.stem + '.{}'.format(ext))
        
        src = (ArcGISSegmentationItemList.from_folder(path/'images')
           .random_split_by_pct(val_split_pct, seed=seed)
           .label_from_func(get_y_func, classes=['NoData'] + list(class_mapping.values()), class_mapping=class_mapping, color_mapping=color_mapping)) #TODO : Handel NoData case

        if transforms is None:
            transforms = get_transforms(flip_vert=True,
                                        max_rotate=90.,
                                        max_zoom=3.0,
                                        max_lighting=0.5) #,
    #                                     xtra_tfms=[skew(direction=(1,8),
    #                                     magnitude=(0.2,0.8))]) 


        data = (src
            .transform(transforms, size=chip_size, tfm_y=True)
            .databunch(bs=batch_size, **databunch_kwargs)
            .normalize(imagenet_stats))
        
    elif dataset_type == 'PASCAL_VOC_rectangles': 


        get_y_func = partial(_get_bbox_lbls, class_mapping=class_mapping)

        src = (SSDObjectItemList.from_folder(path/'images')
           .random_split_by_pct(val_split_pct, seed=seed)
           .label_from_func(get_y_func))

        if transforms is None:
            ranges = (0,1)
            train_tfms = [crop(size=chip_size, p=1., row_pct=ranges, col_pct=ranges), dihedral_affine(), brightness(change=(0.4, 0.6)), contrast(scale=(0.75, 1.5)), rand_zoom(scale=(0.75, 1.5))]
            val_tfms = [crop(size=chip_size, p=1., row_pct=0.5, col_pct=0.5)]
            transforms = (train_tfms, val_tfms)

        data = (src
            .transform(transforms, tfm_y=True)
            .databunch(bs=batch_size, collate_fn=collate_fn, **databunch_kwargs)
            .normalize(imagenet_stats))
        
    elif dataset_type == 'Labeled_Tiles':


        get_y_func = partial(_get_lbls, class_mapping=class_mapping)

        src = (ImageItemList.from_folder(path/'images')
           .random_split_by_pct(val_split_pct, seed=42)
           .label_from_func(get_y_func))

        if transforms is None:
            # transforms = get_transforms(flip_vert=True,
            #                             max_warp=0,
            #                             max_rotate=90.,
            #                             max_zoom=1.5,
            #                             max_lighting=0.5)
            ranges = (0, 1)
            train_tfms = [rotate(degrees=30, p=0.5),
                crop(size=chip_size, p=1., row_pct=ranges, col_pct=ranges), 
                dihedral_affine(), brightness(change=(0.4, 0.6)), contrast(scale=(0.75, 1.5)),
                # rand_zoom(scale=(0.75, 1.5))
                ]
            val_tfms = [crop(size=chip_size, p=1.0, row_pct=0.5, col_pct=0.5)]
            transforms = (train_tfms, val_tfms)

        data = (src
            .transform(transforms, size=chip_size)
            .databunch(bs=batch_size, **databunch_kwargs)
            .normalize(imagenet_stats))
        
    else:
        raise NotImplementedError('Unknown dataset_type="{}".'.format(dataset_type))    

    data.chip_size = chip_size
    data.class_mapping = class_mapping
    data.color_mapping = color_mapping
    show_batch_func = data.show_batch
    show_batch_func = partial(show_batch_func, rows=min(int(math.sqrt(batch_size)), 5))
    data.show_batch = show_batch_func
    data.orig_path = path

    return data
