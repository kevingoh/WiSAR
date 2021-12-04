"""
Utility classes for loading data.
"""

__author__ = "Alexander Krauck"
__email__ = "alexander.krauck@gmail.com"
__date__ = "04-12-2021"

from typing import Optional
import numpy as np
from PIL import Image
from torch.utils.data import Dataset
from torch.utils.data import DataLoader
from matplotlib import pyplot as plt
import os
import json
import cv2


_photo_order = ["B05",
                "B04",
                "B03",
                "B02",
                "B01",
                "G01",
                "G02",
                "G03",
                "G04",
                "G05"]

class MultiViewTemporalSample:
    """The Data Structure to be used for representing single samples of the WISAR challenge.

    An instance contains a numpy array 'photos' that contains the samples,
    with the first dimension for the time (past to present) and the second one for the persepective (left to right).
    Also 'homographies' contains the loaded homography array.
    If mode is validation, also labels will be loaded into the array 'labels'.
    """

    def __init__(self, sample_path: str, mode:str, mask: Optional[np.ndarray] = None) -> None:
        """
        
        Parameters
        ----------
        sample_path: str
            The path of the sample to be loaded into this MutliViewTemporalSample instance.
        mode: str
            Either 'train', 'validation' or 'test'. Only for 'validation' targets will be available.
        mask: Optional[np.ndarray] 
            If not None, this mask is applied.
        """

        homography_dict = json.load(
            open(os.path.join(sample_path, "homographies.json"))
        )

        self.photos = []
        self.homographies = []
        self.mask = mask
        for timestep in range(0, 7):
            timestep_photos = []
            timestep_homographies = []
            for perspective in _photo_order:
                name = str(timestep) + "-" + perspective 
                photo = np.asarray(Image.open(os.path.join(sample_path, name + ".png")))
                homography = homography_dict[name]

                if self.mask is not None:
                    photo[mask] = 0

                timestep_homographies.append(homography)
                timestep_photos.append(photo)
            timestep_photos = np.array(timestep_photos)
            timestep_homographies = np.array(timestep_homographies)
            self.photos.append(timestep_photos)
            self.homographies.append(timestep_homographies)
        self.photos = np.array(self.photos)
        self.homographies = np.array(self.homographies)
        

        if mode == "validation":
            self.labels = np.array(json.load(
                open(os.path.join(sample_path, "labels.json"))
            ))

    def show_photo_grid(self):
        """Show a photo grid of all photos in the sample"""

        fig, ax = plt.subplots(7, 10, figsize=(15, 10))
        for row, timeframe in enumerate(self.photos):
            for col, perspective in enumerate(timeframe):
                ax[row, col].imshow(perspective)
                ax[row, col].axis("off")
                ax[row, col].set_xticklabels([])
                ax[row, col].set_yticklabels([])

        plt.subplots_adjust(wspace=0, hspace=0)
        plt.show()

    def integrate(self, timestep = 0):

        ov_mask = ~self.mask.copy()

        integrated_image = np.zeros((1024,1024,3))

        for photo, homography in zip(self.photos[timestep], self.homographies[timestep]):

            warped_image = cv2.warpPerspective(photo,homography,photo.shape[:2])

            ov_mask = np.where(np.sum(warped_image, axis=-1) > 0, ov_mask, False)
            integrated_image += warped_image

        integrated_image[~ov_mask] = 0 
        integrated_image /= 10

        return np.uint8(integrated_image)

    def draw_labels(self, labels: np.ndarray, on_integrated: bool = False):
        
        if on_integrated:
            image = self.integrate(timestep=3)
        else:
            image = self.photos[3,4]#the center image = 3_B01

        for label in labels:
            image = cv2.rectangle(image, (label[0], label[1]),(label[0]+label[2], label[1]+label[3]),(0,0,255),5)
        
        plt.figure(figsize=(10,10))
        plt.imshow(image)
        plt.show()



class ImageDataset(Dataset):
    """Dataset class that should be used for loading the provided data.
    
    The ImageDataset loads all samples into the memory and stores each sample in a MutliViewTemporalSample instance.
    """

    def __init__(self, data_path: str = "data", mode: str = "train", apply_mask: bool = True):
        """

        Parameters
        ----------
        data_path: str
            The path where all data is included. This means the folder should contain train, test and validation folders and the mask.
        mode: str
            Either 'train', 'validation' or 'test'. Only for 'validation' targets will be available.
        apply_mask: bool
            If True, then the supplied mask will be applied on all pictures.
        #TODO: Lazy loading might be necessary as the data is rather large!
        """

        mode = mode.lower()
        assert mode in ["train", "test", "validation"]

        self.path = os.path.join(data_path, mode)

        if apply_mask:
            mask = ~np.asarray(Image.open(os.path.join("data","mask.png")), dtype=bool)
        else:
            mask = None

        self.samples = [
            MultiViewTemporalSample(os.path.join(self.path, s), mode, mask = mask)
            for s in os.listdir(self.path)
            if os.path.isdir(os.path.join(self.path, s))
        ]
        self.samples = np.array(self.samples)

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index:int):
        return self.samples[index]


#class Pytorch_Dataloader(DataLoader):
    #TODO: Code was useless because the DataLoader should get a Dataset instance and only load the samples there, i.e. minibatch them etc...
    #We might need a custom 'collate_fn' depending on the architecture we choose.

