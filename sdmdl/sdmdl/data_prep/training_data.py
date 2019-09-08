import pandas as pd
import gdal
import numpy as np
import os
import rasterio
import tqdm


class TrainingData:

    """Prepares training datasets using a raster stack, species occurrences and a set of band means and standard
    deviations.

    :param self: a class instance of TrainingData
    :param oh: an Occurrence object: holds occurrence files and tables
    :param gh: a GIS object: holds path names of files required for the computation
    :param verbose: a boolean: prints a progress bar if True, silent if False

    :return: Object. Used to create a series of .csv files (one for each species detected by the Occurrences object)
    containing the input data to the trainer, executed by calling class method create_training_df on TrainingData
    object.
    """

    def __init__(self, oh, gh, verbose):
        self.oh = oh
        self.gh = gh
        self.verbose = verbose

    def prep_training_df(self, src, inras, spec):

        """Loads array from raster stack, locations from species occurrences and band statistics.

        :param self: a class instance of TrainingData
        :param src: rasterio source object for raster stack.
        :param inras: gdal source object for raster stack.
        :param spec: string containing the species name for which the data will be loaded.

        :return: Tuple. Containing:
        string 'spec' that contains the species name for which the files are loaded and returned;
        list 'ppa' contains the status for each loaded occurrence (0 for absence, 1 for presence) for the specified
        species;
        list 'long' and 'lati' contain the longitude and latitude for each occurrence from a specified species;
        list 'row' and 'col' contain the values from the previous 'long' and 'lati' columns converted from WGS84 to
        image coordinates;
        matrix 'myarray' is an multi-dimensional representation of the raster stack;
        table 'mean_std' is an table containing the mean and standard deviation for each of the scaled raster layers
        """

        data = pd.read_csv(self.gh.spec_ppa + '/%s_ppa_dataframe.csv' % spec)
        spec = spec.replace(" ", "_")
        len_pd = np.arange(len(data))
        long = data["dLon"]
        lati = data["dLat"]
        ppa = data["present/pseudo_absent"]
        lon = long.values
        lat = lati.values
        row = []
        col = []
        for i in len_pd:
            row_n, col_n = src.index(lon[i], lat[i])
            row.append(row_n)
            col.append(col_n)
        myarray = inras.ReadAsArray()
        mean_std = pd.read_csv(self.gh.gis + '/env_bio_mean_std.txt', sep="\t")
        mean_std = mean_std.to_numpy()
        return spec, ppa, long, lati, row, col, myarray, mean_std

    def create_training_df(self):

        """Create training dataset by extracting all environmental variables for each occurrence location for a set of
        species.

        :param self: a class instance of TrainingData

        :return: None. Does not return value or object, instead writes the computed training dataset to file for each
        species detected by the Occurrence object (oh).
        """

        src = rasterio.open(self.gh.stack + '/stacked_env_variables.tif')
        inRas = gdal.Open(self.gh.stack + '/stacked_env_variables.tif')
        for i in tqdm.tqdm(self.oh.name, desc='Creating training data' + (28 * ' '), leave=True) if self.verbose else self.oh.name:
            spec, ppa, long, lati, row, col, myarray, mean_std = self.prep_training_df(src, inRas, i)
            X = []
            for j in range(0, self.gh.length):
                band = myarray[j]
                x = []
                for i in range(0, len(row)):
                    value = band[row[i], col[i]]
                    if j < self.gh.scaled_len:
                        if value < -1000:
                            value = np.nan
                        else:
                            value = ((value - mean_std.item((j, 1))) / mean_std.item((j, 2)))
                        x.append(value)
                    if j >= self.gh.scaled_len:
                        if value < -1000:
                            value = np.nan
                        else:
                            value = value
                        x.append(value)
                X.append(x)
            X = np.array([np.array(xi) for xi in X])
            df = pd.DataFrame(X)
            df = df.T
            df["dLat"] = lati
            df["dLon"] = long
            df["present/pseudo_absent"] = ppa
            df["row_n"] = row
            df.rename(columns=dict(zip(df.columns[0:self.gh.length], self.gh.names)), inplace=True)
            df = df.dropna(axis=0, how='any')
            input_data = df
            if not os.path.isdir(self.gh.spec_ppa_env):
                os.makedirs(self.gh.spec_ppa_env, exist_ok=True)
            input_data.to_csv(self.gh.spec_ppa_env + '/%s_env_dataframe.csv' % spec)
