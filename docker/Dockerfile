FROM nvidia/cuda:10.0-cudnn7-runtime-ubuntu18.04 

USER root

RUN apt update
RUN apt install -y python3
RUN apt install -y python3-pip
RUN pip3 install --upgrade pip

RUN apt-get update
RUN apt-get install -y python3-dev
RUN apt-get install -y git

# jupyter
RUN pip3 install jupyter
RUN pip3 install nbdev
RUN pip3 install voila
RUN pip3 install bqplot
RUN pip3 install ipympl
RUN pip3 install ipyvolume
# standard libraries
RUN pip3 install scipy
RUN pip3 install pymongo
RUN pip3 install paramiko
RUN pip3 install scp
RUN pip3 install opencv-python
RUN pip3 install seaborn
RUN pip3 install regex
# machine learning libraries
RUN pip3 install statsmodels
RUN pip3 install scikit-learn
RUN pip3 install scikit-image
RUN pip3 install keras-vis
RUN pip3 install pillow
RUN pip3 install keras
RUN pip3 install tensorflow-gpu==1.14.0
RUN pip3 install torch
RUN pip3 install nbeats-pytorch
RUN pip3 install torch-optimizer
RUN pip3 install fastai
RUN pip3 install --upgrade wandb

# set environment
# needed for weights and biases (shouldn't be need for >python3.7)
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN ln -s /usr/local/cuda-10.0 /usr/local/nvidia

# user id for jupyter
ARG user_id=1000

# MAKE JUPYTER USER
RUN useradd -ms /bin/bash user
RUN usermod -u $user_id user
RUN groupmod -g $user_id user 

# Install Jupyter extensions
RUN pip3 install jupyter_contrib_nbextensions
RUN jupyter contrib nbextension install --user
RUN jupyter nbextensions_configurator enable --user
RUN jupyter nbextension enable collapsible_headings/main --user

# permissions error user -> root
USER root
WORKDIR /home/user

# MAKE DEAFULT CONFIG
RUN jupyter notebook --generate-config
RUN mkdir host_data

# run jupyter notebook automatically
CMD ["sh","-c","jupyter notebook --ip 0.0.0.0 --no-browser --allow-root"]