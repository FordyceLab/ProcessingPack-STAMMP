# title             : chipcollections.py
# description       : 
# authors           : Daniel Mokhtari
# credits           : Craig Markin
# date              : 20180615
# version update    : 20200913
# version           : 0.1.0
# python_version    : 3.7

# General Python
import os
import logging
from glob import glob
from pathlib import Path
from collections import namedtuple, OrderedDict
import pandas as pd

from tqdm import tqdm
from skimage import external

from processingpack.chip import ChipImage



class ChipSeries:
    def __init__(self, device, series_index, attrs = None):
        """
        Constructor for a ChipSeries object.

        Arguments:
            (experiment.Device) device: 
            (int) series_index:
            (dict) attrs: arbitrary ChipSeries metdata

        Returns:
            Return

        """

        self.device = device # Device object
        self.attrs = attrs # general metadata fro the chip
        self.series_indexer = series_index
        self.description = description
        self.chips = {}
        self.series_root = None
        logging.debug('ChipSeries Created | {}'.format(self.__str__()))


    def add_file(self, identifier, path, channel, exposure):
        """
        Adds a ChipImage of the image at path to the ChipSeries, mapped from the passed identifier.
        
        Arguments:
            (Hashable) identifier: a unique chip identifier
            (str) path: image file path
            (str) channel: imaging channel
            (int) exposure: imaging exposure time (ms)

        Returns:
            None

        """

        source = Path(path)
        chipParams = (self.device.corners, self.device.pinlist, channel, exposure)
        self.chips[identifier] = ChipImage(self.device, source, {self.series_indexer:identifier}, *chipParams)
        logging.debug('Added Chip | Root: {}/, ID: {}'.format(source, identifier))


    def load_files(self, root, channel, exposure, indexes = None, custom_glob = None):
        """
        Loads indexed images from a directory as ChipImages. 
        Image filename stems must be of the form *_index.tif. 
        
        Arguments:
            (str) root: directory path containing images
            (str) channel: imaging channel
            (int) exposure: imaging exposure time (ms)
            (list | tuple) indexes: custom experimental inde

        Returns:
            None

        """

        self.series_root = root
        
        glob_pattern = '*StitchedImg*.tif'
        if custom_glob:
            glob_pattern = custom_glob
        
        if not indexes:
            r = Path(root)
            img_files = [i for i in list(r.glob(glob_pattern)) if not 'ChamberBorders'in i.stem or 'Summary' in i.stem]
            img_paths = [Path(os.path.join(r.parent, img)) for img in img_files]
            try:
                record = {int(path.stem.split('_')[-1]):path for path in img_paths}
            except ValueError:
                logging.info('WARNING: Coerced image indexes to floats')
                record = {float(path.stem.split('_')[-1]):path for path in img_paths}
            chipParams = (self.device.corners, self.device.pinlist, channel, exposure)
            self.chips = {identifier:ChipImage(self.device, source, 
                {self.series_indexer:identifier}, *chipParams) for identifier, source in record.items()
            }
            
            keys = list(self.chips.keys())
            logging.debug('Loaded Series | Root: {}/, IDs: {}'.format(root, keys))


    def summarize(self):
        """
        Summarize the ChipSeries as a Pandas DataFrame for button and/or chamber features
        identified in the chips contained.

        Arguments:
            None

        Returns:
            (pd.DataFrame) summary of the ChipSeries

        """

        summaries = []
        for i, r in self.chips.items():
            df = r.summarize()
            df[self.series_indexer] = i
            summaries.append(df)
        return pd.concat(summaries).sort_index()


    def map_from(self, reference, mapto_args = {}):
        """
        Maps feature positions from a reference chip.ChipImage to each of the ChipImages in the series.
        Specific features can be mapped by passing the optional mapto_args to the underlying 
        mapper.

        Arguments:
            (chip.ChipImage) reference: reference image (with found button and/or chamber features)
            (dict) mapto_args: dictionary of keyword arguments passed to ChipImage.mapto().

        Returns:
            None

        """

        for chip in tqdm(self.chips.values(), desc = 'Series <{}> Stamped and Mapped'.format(self.description)):
            chip.stamp()
            reference.mapto(chip, **mapto_args)


    def from_record():
        """
        TODO: Import imaging from a Stitching record.
        """
        return


    def _repr_pretty_(self, p, cycle = True):
        p.text('<{}>'.format(self.device.__str__()))


    def save_summary(self, outPath = None):
        """
        Generates and exports a ChipSeries summary Pandas DataFrame as a bzip2 compressed CSV file.
        
        Arguments:
            (str) outPath: target directory for summary

        Returns:
            None

        """

        target = self.series_root
        if outPath:
            target = outPath
        df = self.summarize()
        fn = '{}_{}_{}.csv.bz2'.format(self.device.dname, self.description, 'ChipSeries')
        df.to_csv(os.path.join(target, fn), compression = 'bz2')


    def save_summary_images(self, outPath = None, featuretype = 'chamber'):
        """
        Generates and exports a stamp summary image (chip stamps concatenated)
        
        Arguments:
            (str) outPath: user-define export target directory
            (str) featuretype: type of feature overlay ('chamber' | 'button')

        Returns:
            None

        """

        target_root = self.series_root
        if outPath:
            target_root = outPath
        target = os.path.join(target_root, 'SummaryImages') # Wrapping folder
        os.makedirs(target, exist_ok=True)
        for c in self.chips.values():
            image = c.summary_image(featuretype)
            name = '{}_{}.tif'.format('Summary', c.data_ref.stem)
            outDir = os.path.join(target, name)
            external.tifffile.imsave(outDir, image)
        logging.debug('Saved Summary Images | Series: {}'.format(self.__str__()))


    def _delete_stamps(self):
        """
        Deletes and forces garbage collection of stamps for all ChipImages
        
        Arguments:
            None

        Returns:
            None

        """

        for c in self.chips.values():
            c._delete_stamps()


    def repo_dump(self, target_root, title, as_ubyte = False, featuretype = 'button'):
        """
        Save the chip stamp images to the target_root within folders title by chamber IDs

        Arguments:
            (str) target_root:
            (str) title:
            (bool) as_ubyte:

        Returns:
            None

        """

        for i, c in self.chips.items():
            title = '{}{}_{}'.format(self.device.setup, self.device.dname, i)
            c.repo_dump(featuretype, target_root, title, as_ubyte = as_ubyte)

    def __str__(self):
        return ('Description: {}, Device: {}'.format(self.description, str((self.device.setup, self.device.dname))))



class StandardSeries(ChipSeries):
    def __init__(self, device, description, attrs = None):
        """
        Constructor for a StandardSeries object.

        Arguments:
            (experiment.Device) device: Device object
            (str) description: Terse description (e.g., 'cMU')
            (dict) attrs: arbitrary StandardSeries metadata

        Returns:
            None

        """

        self.device = device # Device object
        self.attrs = attrs # general metadata fro the chip
        self.series_indexer = 'concentration_uM'
        self.description = description
        self.chips = None
        self.series_root = None
        logging.debug('StandardSeries Created | {}'.format(self.__str__()))
    
    def get_hs_key(self):
        return max(self.chips.keys())

    def get_highstandard(self):
        """
        Gets the "maximal" (high standard) chip object key

        Arguments:
            None

        Returns:
            None

        """


        return self.chips[self.get_hs_key()]
    

    def map_from_hs(self, mapto_args = {}):
        """
        Maps the chip image feature position from the StandardSeries high standard to each 
        other ChipImage
        
        Arguments:
            (dict) mapto_args: dictionary of keyword arguments passed to ChipImage.mapto().

        Returns:
            None

        """

        reference_key = {self.get_hs_key()}
        all_keys = set(self.chips.keys())
        hs = self.get_highstandard()
        
        for key in tqdm(all_keys - reference_key, desc = 'Processing Standard <{}>'.format(self.__str__())):
            self.chips[key].stamp()
            hs.mapto(self.chips[key], **mapto_args)


    def process(self, featuretype = 'chamber'):
        """
        A high-level (script-like) function to execute analysis of a loaded Standard Series.
        Processes the high-standard (stamps and finds chambers) and maps processed high standard
        to each other ChipImage
        
        Arguments:
            (str) featuretype: stamp feature to map

        Returns:
            None

        """

        hs = self.get_highstandard()
        hs.stamp()
        hs.findChambers()
        self.map_from_hs(mapto_args = {'features': featuretype})
    

    def process_summarize(self):
        """
        Simple wrapper to process and summarize the StandardSeries Data

        Arguments:
            None

        Returns:
            None

        """

        self.process()
        df =  self.summarize()
        return df


    def save_summary(self, outPath = None):
        """
        Generates and exports a StandardSeries summary Pandas DataFrame as a bzip2 compressed CSV file.
        
        Arguments:
            (str | None) outPath: target directory for summary. If None, saves to the series root.

        Returns:
            None

        """

        target = self.series_root
        if outPath:
            target = outPath
        df = self.summarize()
        fn = '{}_{}_{}.csv.bz2'.format(self.device.dname, self.description, 'StandardSeries_Analysis')
        df.to_csv(os.path.join(target, fn), compression = 'bz2')
        logging.debug('Saved StandardSeries Summary | Series: {}'.format(self.__str__()))




class ChipQuant:
    def __init__(self, device, description, attrs = None):
        """
        Constructor for a ChipQuant object
       
        Arguments:
            (experiment.Device) device: device object
            (str) description: terse user-define description
            (dict) attrs: arbitrary metadata

        Returns:
            None

        """

        self.device = device
        self.description = description
        self.attrs = attrs
        self.chip = None
        self.processed = False
        logging.debug('ChipQuant Created | {}'.format(self.__str__()))


    def load_file(self, path, channel, exposure):
        """
        Loads an image file as a ChipQuant.
        
        Arguments:
            (str) path: path to image
            (str) channel: imaging channel
            (int) exposure: exposure time (ms)

        Returns:
            None

        """

        p = Path(path)
        chipParams = (self.device.corners, self.device.pinlist, channel, exposure)
        self.chip = ChipImage(self.device, p, {}, *chipParams)
        logging.debug('ChipQuant Loaded | Description: {}'.format(self.description))


    def process(self, reference = None, mapped_features = 'button'):
        """
        Processes a chip quantification by stamping and finding buttons. If a reference is passed,
        button positions are mapped.
        
        Arguments:
            (ChipImage) button_ref: Reference ChipImage
            (st) mapped_features: features to map from the reference (if button_ref)

        Returns:
            None

        """

        self.chip.stamp()
        if not reference:
            if mapped_features == 'button':
                self.chip.findButtons()
            elif mapped_features == 'chamber':
                self.chip.findChambers()
            elif mapped_features == 'all':
                self.chip.findButtons()
                self.chip.findChambers()
            else:
                raise ValueError('Must specify valid feature name to map ("button", "chamber", or "all"')
        else:
            reference.mapto(self.chip, features = mapped_features)
        self.processed = True
        logging.debug('Features Processed | {}'.format(self.__str__()))


    def summarize(self):
        """
        Summarize the ChipQuant as a Pandas DataFrame for button features
        identified in the chips contained.

        Arguments:
            None

        Returns:
            (pd.DataFrame) summary of the ChipSeries

        """

        if self.processed:
            return self.chip.summarize()
        else:
            raise ValueError('Must first process ChipQuant')


    def process_summarize(self, reference = None, process_kwrds = {}):
        """
        Script-like wrapper for process() and summarize() methods
        
        Arguments:
            (chip.ChipImage) reference: ChipImage to use as a reference
            (dict) process_kwrds: keyword arguments passed to ChipQuant.process()

        Returns:
            (pd.DataFrame) summary of the ChipSeries
        

        """
        self.process(reference = reference, **process_kwrds)
        return self.summarize()


    def save_summary_image(self, outPath_root = None):
        """
        Generates and exports a stamp summary image (chip stamps concatenated)

        Arguments:
            (str) outPath_root: path of user-defined export root directory

        Returns:
            None

        """

        outPath = self.chip.data_ref.parent
        if outPath_root:
            if not os.isdir(outPath_root):
                em = 'Export directory does not exist: {}'.format(outPath_root)
                raise ValueError(em)
            outPath = Path(outPath_root)

        target = os.path.join(outPath, 'SummaryImages') # Wrapping folder
        os.makedirs(target, exist_ok=True)
        
        c = self.chip
        image = c.summary_image('button')
        name = '{}_{}.tif'.format('Summary', c.data_ref.stem)
        outDir = os.path.join(target, name)
        external.tifffile.imsave(outDir, image)
        logging.debug('Saved ChipQuant Summary Image | ChipQuant: {}'.format(self.__str__()))


    def repo_dump(self, outPath_root, as_ubyte = False):
        """
        Export the ChipQuant chip stamps to a repository (repo). The repo root contains a 
        directory for each unique pinlist identifier (MutantID, or other) and subdirs
        for each chamber index. Stamps exported as .png
        
        Arguments:
            (str): outPath_root: path of user-defined repo root directory
            (bool) as_ubyte: flag to export the stamps as uint8 images

        Returns:
            None

        """

        title = '{}{}_{}'.format(self.device.setup, self.device.dname, self.description)
        self.chip.repo_dump('button', outPath_root, title, as_ubyte = as_ubyte)
    

    def __str__(self):
        return ('Description: {}, Device: {}'.format(
            self.description, str((self.device.setup, self.device.dname))))


