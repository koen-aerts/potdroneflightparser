FROM python:3.11.10-bookworm

RUN useradd -m -U builder; \
    apt update; \
    apt install -y git zip unzip sudo openjdk-17-jdk python3-pip python3-setuptools python3-dev patch autoconf automake build-essential libtool pkg-config gettext zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libltdl-dev libssl-dev; \
    apt remove ccache;

USER builder
WORKDIR /home/builder
RUN mkdir source

COPY --chown=builder:builder ./ ./source/

RUN echo "export PATH=$PATH:~/.local/bin/" >> .profile; \
    echo "export PATH=$PATH:~/.local/bin/" >> .bashrc; \
    export PATH=$PATH:~/.local/bin/; \
    pip3 install --upgrade buildozer; \
    pip3 install --upgrade Cython==0.29.37 wheel pip setuptools virtualenv; \
    git clone https://github.com/kivy/python-for-android.git; \
    cd source; \
    yes | buildozer android debug; \
    sh -c "rm -Rf *";

VOLUME /home/builder/source
