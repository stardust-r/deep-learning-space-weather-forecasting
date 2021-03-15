# A Deep Learning Approach to Solar Radio Flux Forecasting

27-day forecasting of the F10.7 solar flux using [N-BEATS](https://openreview.net/forum?id=r1ecqn4YwB) deep residual neural network with forecast uncertainties provided using deep ensembles.

## Repository Structure

1. Model architecture, training and evaluation methods in jupyter notebook form in nbs directory.
1. Ensemble runs from wandb sweeps directory using .py (generated automatically using nbdev in lib directory) and .yaml configuration file.
1. Sweep runs available for download from [wandb](https://wandb.ai/stardust-r/deep-learning-space-weather-forecasting) to be used for ensembling, analysis and plotting in nbs.


## Data

Sources of data used in this work:

- ESA Space Weather Service: https://swe.ssa.esa.int/
>> space surveillance and tracking service

>> archive of geomagnetic and solar activity indices for drag calculation

>> products: F10.7 archive of SGIArv

- CLS Prediction Service: https://spaceweather.cls.fr/services/radioflux/


## Docker

Build image for docker environment using provided Dockerfile, and run (GPU enabled) as:

```
docker run --gpus all -d -p 8866:8888 -v ~:/home/user --name <container name> <image>
```


## Citation

If you use this code in any context, please cite the following paper: 

```
Stevenson, E., Rodriguez-Fernandez, V., Minisci, E., Camacho, D. (2020). A Deep Learning Approach to Space Weather Proxy Forecasting for Orbital Prediction. In Proceedings of the 71st International Astronautical Congress (IAC), The CyberSpace Edition, 12-14 October 2020.
```
