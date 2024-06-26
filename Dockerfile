# Start with the lastest ubuntu, for a solid base,
# since we need some advance binaries for things like pillow and ffmpeg.
FROM ubuntu:latest

# We will base ourselves in root, becuase why not.
WORKDIR /root

# Define some user vars we will use for the image.
# These are read in the docker_octoeverywhere module, so they must not change!
ENV USER=root
ENV REPO_DIR=/root/octoeverywhere
ENV VENV_DIR=/root/octoeverywhere-env
# This is a special dir that the user MUST mount to the host, so that the data is persisted.
# If this is not mounted, the printer will need to be re-linked everytime the container is remade.
ENV DATA_DIR=/data/

# Install the required packages.
# Any packages here should be mirrored in the install script - and any optaionl pillow packages done inline.
RUN apt update
RUN apt install -y curl ffmpeg jq python3 python3-pip python3-venv virtualenv libjpeg-dev zlib1g-dev python3-pil python3-pillow

#
# We decided to not run the installer, since the point of the installer is to setup the env, build the launch args, and setup the serivce.
# Instead, we will manually run the smaller subset of commands that are requred to get the env setup in docker.
# Note that if this ever becomes too much of a hassle, we might want to revert back to using the installer, and supporting a headless install.
#
RUN virtualenv -p /usr/bin/python3 ${VENV_DIR}
RUN ${VENV_DIR}/bin/python -m pip install --upgrade pip

# Copy the entire repo into the image, do this as late as possible to avoid rebuilding the image everytime the repo changes.
COPY ./ ${REPO_DIR}/
RUN ${VENV_DIR}/bin/pip3 install --require-virtualenv --no-cache-dir -q -r ${REPO_DIR}/requirements.txt

# For docker, we use our docker_octoeverywhere host to handle the runtime setup and launch of the serivce.
WORKDIR ${REPO_DIR}
# Use the full path to the venv, we msut use this [] notation for our ctlc handler to work in the contianer
ENTRYPOINT ["/root/octoeverywhere-env/bin/python", "-m", "docker_octoeverywhere"]