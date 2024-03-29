# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/06_ensemble_utils.ipynb (unless otherwise specified).

__all__ = ['fdownload_wandb_files', 'fget_pickled', 'fget_preds', 'fensemble', 'fensemble_boosting_regressor', 'fmse',
           'fmape', 'fcc_pearsonr', 'frmse', 'fmae', 'fme', 'fmse_std', 'fmape_std', 'fcc_pearsonr_std', 'frmse_std',
           'fmae_std', 'fme_std', 'fget_metrics', 'fget_metrics_std', 'fget_external_forecasts',
           'fget_external_metrics']

# Cell
import pandas as pd
import numpy as np
import datetime as dt
import matplotlib as mpl
import matplotlib.pyplot as plt
import pickle
import pathlib
import wandb
from pathlib import Path

from sklearn.metrics import mean_squared_error, mean_absolute_error
from scipy.stats import pearsonr
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import GradientBoostingRegressor

from .read_data import *
from .stats_utils import cErrorMetrics, cStationary

# Cell
def fdownload_wandb_files(api, entity, project, sweep_ids, datadirs, wandbfname="preds_test_fname"):
    """
    download files with fname for all runs associated with list of sweep_ids into datadirs

    output:
    data[run_id] = [path, run.config]
    """
    data = {}

    for i in range(len(sweep_ids)):
        sweep = api.sweep("{}/{}/{}".format(entity, project, sweep_ids[i]))
        print("Sweep: ", sweep.config["name"])

        datadir = pathlib.Path(datadirs[i])
        datadir.mkdir(parents=True, exist_ok=True)

        for run in sweep.runs:
            run_id = run.id

            # fname on wandb api same for each run, need to rename with run_id
            fname_todownload = run.config[wandbfname]#.split("/")[1]
            fname_downloaded = "{}_{}.{}".format(fname_todownload.split(".")[0], run_id, fname_todownload.split(".")[1])

            # download (if doesn't already exist) and rename
            if not (datadir/fname_downloaded).is_file():
                file = run.file(fname_todownload)
                print("{} downloading {}...".format(run_id, fname_todownload))
                file.download(replace=False, root=datadir)
                (datadir/fname_todownload).rename(datadir/fname_downloaded)
            else:
                print("{} already downloaded.".format(fname_downloaded))

            # store location of file and run info
            data[run_id] = [datadir/fname_downloaded, run.config]

        return data

# Cell
def fget_pickled(sweeps, datadir, entity, project, pklname="models/preds_test.pickle",
                 download=True, sweep_type="txt"):
    """
    download pickle files associated with runs in sweeps
    read data into dictionary first broken down by horizon, then indiviual runs

    sweep_type: "api" or "txt" [for manual .txt files with sweep run ids]
    sweeps == list of sweep ids or list of paths/filenames containing run ids
    """
    # path to download files to
    datadir = Path(datadir)
    datadir.mkdir(parents=True, exist_ok=True)

    api = wandb.Api()

    data = {}
    for sweep_i in sweeps:

        # case of wandb api working correctly:
        if sweep_type == "api":
            sweep = api.sweep("{}/{}/{}".format(entity, project, sweep_i))
            runs  = sweep.runs
            lrun  = len(runs)

        # case of txt files containing list of run_ids:
        elif sweep_type == "txt":
            df = pd.read_csv(sweep_i, delimiter=", ")
            run_ids = df["ID"].to_numpy().flatten()
            horizon = df["H"].to_numpy().flatten()
            lrun = len(run_ids)

        print(sweep_i, lrun)

        for i in range(lrun):

            if sweep_type == "api":
                run = runs[i]
                run_id = run.id
                h = run.config["horizon"]

            elif sweep_type == "txt":
                run_id = run_ids[i]
                # need access to run.config to get horizon (this is slow...)
                #run = api.run("{}/{}/{}".format(entity, project, run_id))
                h = horizon[i]

            # need to change name to include run_id or will overwrite
            fname_todownload = pklname
            fname_downloaded = "{}_{}.{}".format(fname_todownload.split(".")[0], run_id, fname_todownload.split(".")[1])

            # download pickle file (if doesn't already exist)
            if download:
                if not (datadir/fname_downloaded).is_file():
                    file = run.file(fname_todownload)
                    print("{} downloading {}...".format(run_id, fname_todownload))
                    file.download(replace=False, root=datadir)
                    (datadir/fname_todownload).rename(datadir/fname_downloaded)
                else:
                    print("{} already downloaded.".format(fname_downloaded))

            # read in pickle
            with open(datadir/fname_downloaded, 'rb') as handle:
                d = pickle.load(handle)

            # store by horizon, run_id
            try:
                data[h][run_id] = d
            except KeyError:
                data[h] = {}
                data[h][run_id] = d

    return data

# Cell
def fget_preds(subdict, limit_date=False, lcompdate=None, ucompdate=None):
    """
    stack predictions over ensemble runs
    get predictions and targets from runs
    shape: (90, 20729, 3) (n_ensemble_runs, n_windows, H)

    limit_date to crop for comparison with cls, esa etc.
    """
    # shorter lookbacks have more predictions
    # need to ensure all predictions are of same length and are combining the right set of predictions
    common_idx = []
    for run_id in subdict.keys():
        common_idx.append(len(subdict[run_id]["pred_date"]))
    idx = min(common_idx)

    # get common targets and prediction dates
    keys  = list(subdict.keys())
    targs = subdict[keys[0]]["targs_denorm"][-idx:]
    epoch = subdict[keys[0]]["pred_date"][-idx:]

    if limit_date:
        try:
            larg = np.argwhere(epoch==lcompdate)[0][0]
        except IndexError:
            larg = 0
        try:
            uarg = np.argwhere(epoch==ucompdate)[0][0] + 1
        except IndexError:
            uarg = -1
        targs = targs[larg:uarg]
        epoch = epoch[larg:uarg]

    # get predictions for each run
    preds = []
    for run_id in subdict.keys():
        if limit_date:
            preds.append(subdict[run_id]["preds_denorm"][-idx:][larg:uarg])
        else:
            preds.append(subdict[run_id]["preds_denorm"][-idx:])
    print(np.array(preds).shape, epoch[0], epoch[-1])

    return np.array(epoch), np.array(preds), np.array(targs)

# Cell
def fensemble(preds_valid, mode="mean"):
    """
    simple mean/median ensemble, std over ensemble
    """
    # reshape
    stack = np.dstack(preds_valid)

    if mode == "mean":
        ensemble_preds = np.mean(stack, axis=2)
    elif mode == "median":
        ensemble_preds = np.median(stack, axis=2)

    # variance in ensemble
    ensemble_std = np.std(stack, axis=2)
    #print(ensemble_std.shape)

    return ensemble_preds, ensemble_std

# Cell
def fensemble_boosting_regressor(preds_valid, targs_valid, preds_train, targs_train, alpha=0.9):
    """
    Learn combination of ensemble members from training data using Gradient Boosting Regression
    Also provides prediction intervals (using quantile regression)
    alpha = % prediction interval

    https://scikit-learn.org/stable/auto_examples/ensemble/plot_gradient_boosting_quantile.html
    https://towardsdatascience.com/how-to-generate-prediction-intervals-with-scikit-learn-and-python-ab3899f992ed
    """
    ensemble_preds = []
    ensemble_lower = []
    ensemble_upper = []

    H = preds_valid.shape[2]

    # run for each day over horizon
    for h in range(H):

        X_train = preds_train[:,:,h].T
        y_train = targs_train[:,h]
        X_test = preds_valid[:,:,h].T
        y_test = targs_valid[:,h]

        upper_model = GradientBoostingRegressor(loss="quantile", alpha=alpha)
        mid_model   = GradientBoostingRegressor(loss="ls")
        lower_model = GradientBoostingRegressor(loss="quantile", alpha=(1.0-alpha))

        # fit models
        lower_model.fit(X_train, y_train)
        mid_model.fit(X_train, y_train)
        upper_model.fit(X_train, y_train)

        # store predictions
        ensemble_preds.append(mid_model.predict(X_test))
        ensemble_lower.append(lower_model.predict(X_test))
        ensemble_upper.append(upper_model.predict(X_test))

    return np.stack(ensemble_preds).T, np.stack(ensemble_lower).T, np.stack(ensemble_upper).T

# Cell
def fmse(y_true, y_pred):
    """
    Mean square error.
    (from sklearn.metrics import mean_squared_error)
    """
    # return np.sum( (np.array(y_true) - np.array(y_pred))**2 ) / len(y_true)
    return mean_squared_error(y_true, y_pred)

def fmape(y_true, y_pred):
    """
    mean_absolute_percentage_error.
    (can cause division-by-zero errors)
    """
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    return np.mean(np.abs((y_true - y_pred) / y_true)) * 100

def fcc_pearsonr(y_true, y_pred):
    """
    pearson correlation coefficient
    """
    try:
        return pearsonr(y_true, y_pred)
    except TypeError:
        return pearsonr(y_true.flatten(), y_pred.flatten())

def frmse(y_true, y_pred):
    """
    Root mean square error.
    (from sklearn.metrics import mean_squared_error)
    """
    return np.sqrt(mean_squared_error(y_true, y_pred))

def fmae(y_true, y_pred):
    """
    mean absolute error
    """
    #return np.sum( np.abs(np.array(y_true) - np.array(y_pred)) ) / len(y_true)
    return mean_absolute_error(y_true, y_pred)

def fme(y_true, y_pred):
    """
    bias
    see Liemohn 2018 (model - observed)
    """
    return np.sum( np.array(y_pred) - np.array(y_true) ) / len(y_true)

# Cell
def fmse_std(y_true, y_pred):
    """
    Mean square error.
    (from sklearn.metrics import mean_squared_error)
    There mse stds are massive: would need to plot using rmse
    """
    se = (np.array(y_true) - np.array(y_pred))**2
    mse = np.mean(se)#, axis=0
    sdse = np.std(se)#, axis=0
    return sdse

def fmape_std(y_true, y_pred):
    """
    mean_absolute_percentage_error.
    (can cause division-by-zero errors)
    """
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    ape = np.abs((y_true - y_pred) / y_true)
    mape = np.mean(ape) * 100
    sdape = np.std(ape) * 100
    return sdape

def fcc_pearsonr_std(y_true, y_pred):
    """
    pearson correlation coefficient
    """
    return np.nan

def frmse_std(y_true, y_pred):
    """
    Root mean square error.
    (from sklearn.metrics import mean_squared_error)
    """
    se = (np.array(y_true) - np.array(y_pred))**2
    mse = np.mean(se)#, axis=0
    sdse = np.std(se)#, axis=0
    return np.sqrt(sdse)

def fmae_std(y_true, y_pred):
    """
    mean absolute error
    """
    ae = np.abs(np.array(y_true) - np.array(y_pred))
    mae = np.mean(ae)#, axis=0
    sdae = np.std(ae)#, axis=0
    return sdae

def fme_std(y_true, y_pred):
    """
    bias
    see Liemohn 2018 (model - observed)
    """
    e = np.array(y_pred) - np.array(y_true)
    me = np.mean(e)#, axis=0
    sde = np.std(e)#, axis=0
    return sde

# Cell
def fget_metrics(y_pred, y_true):
    return [fmse(y_true, y_pred), fmape(y_true, y_pred), fcc_pearsonr(y_true, y_pred)[0],
            frmse(y_true, y_pred), fmae(y_true, y_pred), fme(y_true, y_pred)]

def fget_metrics_std(y_pred, y_true):
    return [fmse_std(y_true, y_pred), fmape_std(y_true, y_pred), fcc_pearsonr_std(y_true, y_pred),
            frmse_std(y_true, y_pred), fmae_std(y_true, y_pred), fme_std(y_true, y_pred)]

# Cell
def fget_external_forecasts(config):
    """
    generate dataframe containing forecasts and "truths" for external sources
    get persistence

    test:
    #config = AttrDict()
    #config.update(user_config)
    #fget_external_forecasts(config)
    """
    # ESA
    if "esa" in config.data_comp:
        dataobj_esa = cESA_SWE()
        # read in archive data
        df = dataobj_esa.fget_data(filenames=config.esa_archive_fname)[config.esa_archive_key]
        df.set_index('ds', inplace=True)
        udate_a = (dt.datetime.strptime(config.date_ulim, "%Y-%m-%d") + dt.timedelta(days=27)).strftime("%Y-%m-%d")
        df_lim = df[config.date_llim:udate_a]
        #dfa_esa = dataobj_esa.finterpolate(df_lim, config.interp_freq)
        df_daily = dataobj_esa.fget_daily(df_lim, config.get_daily_method)
        dfa_esa  = dataobj_esa.fmissing_data(df_daily, config.missing_data_method)
        # read in esa forecast data
        dff_esa = dataobj_esa.fget_data(filenames=config.esa_forecast_fname)[config.esa_forecast_key]
        # add "truth" from archive to forecast
        dff_comp_esa = dataobj_esa.fget_forecast_comp(dff_esa, dfa_esa, cname="y")

        # rename columns
        #dfa_esa.columns = ['gendate' , 'ds', 'y_esa_true']
        dff_comp_esa.columns = ['gendate' , 'ds', 'y_esa', 'y_esa_true']
        # Calculate persistence
        #dff_comp_esa = dataobj_esa.fget_persistence(dfa_esa, 'y_esa_true', "persistence_esa")
        dff_comp_esa = dataobj_esa.fget_persistence(dff_comp_esa, 'y_esa_true', "persistence_esa")

    # CLS-CNES
    if "cls" in config.data_comp:
        dataobj_cls = cCLS_CNES()
        # read in archive data and restrict to ds and key variable
        # need to ensure upper date for archive is 30 days ahead of upper date of forecast gendate
        udate_a = (dt.datetime.strptime(config.cls_forecast_udate, "%Y-%m-%d") + dt.timedelta(days=30)).strftime("%Y-%m-%d")
        dfa_cls = dataobj_cls.fget_archive_data(config.cls_datadir, config.cls_forecast_ldate, udate_a)
        dfa_cls = dfa_cls[['ds',config.cls_key]]
        dfa_cls = dfa_cls.set_index("ds")
        # read in forecast data and restrict to key variable
        dff_cls = dataobj_cls.fget_forecast_data(config.cls_datadir, config.cls_forecast_ldate, config.cls_forecast_udate)

        dff_cls = dff_cls[['gendate', 'ds', "{}_c".format(config.cls_key)]]
        # add "truth" from archive to forecast
        dff_comp_cls = dataobj_cls.fget_forecast_comp(dff_cls, dfa_cls, cname=config.cls_key)

        # rename columns
        dff_comp_cls.columns = ['gendate' , 'ds', 'y_cls', 'y_cls_true']
        # Calculate persistence
        dff_comp_cls = dataobj_cls.fget_persistence(dff_comp_cls, 'y_cls_true', "persistence_cls")

        # botch
        # include esa persistence in cls only table
        if "esa" not in config.data_comp:
            dataobj_esa = cESA_SWE()
            # read in archive data
            df = dataobj_esa.fget_data(filenames=config.esa_archive_fname)[config.esa_archive_key]
            df.set_index('ds', inplace=True)

            ldate = (dt.datetime.strptime(config.cls_forecast_ldate, "%Y-%m-%d") - dt.timedelta(days=1)).strftime("%Y-%m-%d")
            df_lim = df[ldate:udate_a] # hard code as takes 1 day later for some reason
            #dfa_esa = dataobj_esa.finterpolate(df_lim, config.interp_freq)
            df_daily = dataobj_esa.fget_daily(df_lim, config.get_daily_method)
            dfa_esa  = dataobj_esa.fmissing_data(df_daily, config.missing_data_method)
            # add "truth" from archive to forecast
            dff_comp_cls1 = dataobj_cls.fget_forecast_comp(dff_cls, dfa_esa, cname="y_cls")

            dff_comp_cls1.columns = ['gendate' , 'ds', 'y_cls', 'y_esa_true']

            # drop gendates that don't give full forcast (depends on horizon)
            dff_comp_cls1 = dff_comp_cls1[dff_comp_cls1.groupby('gendate').gendate.transform('count')>=27].copy()

            # Calculate persistence
            dff_comp_cls1 = dataobj_cls.fget_persistence(dff_comp_cls1, 'y_esa_true', "persistence_esa")

            dff_comp_cls = pd.merge(dff_comp_cls, dff_comp_cls1, on=['gendate', 'ds', 'y_cls'])


    # COMBINE AND RETURN
    if ("esa" in config.data_comp) and ("cls" in config.data_comp):
        df_comp = pd.merge(dff_comp_esa, dff_comp_cls, on=['gendate', 'ds'])
        return df_comp
    elif "esa" in config.data_comp:
        return dff_comp_esa
    elif "cls" in config.data_comp:
        return dff_comp_cls

# Cell
def fget_external_metrics(dff, config):
    metrics = {}
    metrics_std = {}

    if "esa" in config.data_comp:
        metrics["ESA"] = fget_metrics(dff.y_esa, dff.y_esa_true)
        metrics_std["ESA"] = fget_metrics_std(dff.y_esa, dff.y_esa_true)

    if "cls" in config.data_comp:
        metrics["CLS"] = fget_metrics(dff.y_cls, dff.y_cls_true)
        metrics_std["CLS"] = fget_metrics_std(dff.y_cls, dff.y_cls_true)

    metrics["PERSISTENCE"] = fget_metrics(dff.persistence_esa, dff.y_esa_true)
    metrics_std["PERSISTENCE"] = fget_metrics_std(dff.persistence_esa, dff.y_esa_true)
    #metrics["PERSISTENCE"] = fget_metrics(dff.persistence_cls, dff.y_cls_true)

    return metrics, metrics_std