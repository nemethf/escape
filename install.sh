#!/bin/bash

# This script should run in this VM:
# https://bitbucket.org/mininet/mininet-vm-images/downloads/mininet-2.1.0-130919-ubuntu-13.04-server-amd64-ovf.zip
#
# The newer one with ubuntu 14.04 seems to produce strange random
# errors when we run click/clicky.
# (http://onlab.vicci.org/mininet-vm/mininet-2.1.0p2-140718-ubuntu-14.04-server-amd64-ovf.zip)
#

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
install='sudo apt-get -y install'
sshd_config_file='/etc/ssh/sshd_config'

# 13.04 is now in the old-releases.
if [ $(lsb_release -r|cut -f2) == 13.04 ]; then
    apt_file=/etc/apt/sources.list
    sudo sed -i -s 's/mirrors.kernel.org/old-releases.ubuntu.com/' $apt_file
    sudo sed -i -s 's/security.ubuntu.com/old-releases.ubuntu.com/' $apt_file
fi

sudo apt-get update

##
## general
##
$install \
    xserver-xorg-video-vmware xinit x11-xserver-utils \
    fluxbox

##
## autologin
##

file=/etc/init/tty1.conf
if ! grep -q autologin $file; then
   sudo sed -i -e 's/sbin\/getty/sbin\/getty --autologin mininet/' $file
fi
file=~/.profile
if ! grep -q on.tty1 $file; then
   cat <<EOF >>$file
#start x automatically on tty1
test \$(tty) == /dev/tty1 && exec startx
EOF
fi

##
## VirtualBox Guest Additions
##
sudo mount /dev/cdrom /mnt
cd /mnt
if [ -f ./VBoxLinuxAdditions.run ]; then
    sudo ./VBoxLinuxAdditions.run
else
    $install virtualbox-guest-additions
fi
sudo umount /mnt

##
## GUI
##

$install python-networkx python-imaging-tk

##
## Click
##

# for clicky 
$install graphviz

# Download click from git and compile
# TODO: instead of HEAD, we should clone a version known to work.
cd
git clone --depth 1 https://github.com/kohler/click.git
cd click
./configure --disable-linuxmodule
CPU=$(grep -c '^processor' /proc/cpuinfo)
make -j$CPU
sudo make install

cd apps/clicky
autoreconf -i
./configure 
make -j$CPU
sudo make install
cd ../..

make clean

# install clickhelper.py to be availble from netconfd
cd /usr/local/bin
sudo ln -s "$DIR/mininet/mininet/clickhelper.py" .

##
## OpenYuma
##
# This will install all dependencies for NETCONF
$install \
    libxml2-dev libssh2-1-dev libgcrypt11-dev libncurses5-dev \
    make gcc automake \
    openssh-client openssh-server ssh
#git clone https://github.com/OpenClovis/OpenYuma.git
cd "$DIR/OpenYuma"
make
sudo make install

#we need to setup the ssh server with more than one port for NETCONF
cat <<EOF | sudo tee -a $sshd_config_file
# ----- NETCONF -----
Port 830
Port 831
Port 832
Subsystem netconf /usr/sbin/netconf-subsystem
# --- END NETCONF ---
EOF
#restarting ssh server
sudo /etc/init.d/ssh restart

cd "$DIR/Unify_ncagent/vnf_starter"
mkdir -p bin
mkdir -p lib
sudo cp vnf_starter.yang /usr/share/yuma/modules/
make
sudo make install
make clean

##
## NCCLIENT
##

# Requirements:
# <= 2.6 python < 3
# python-setuptools 0.6+
# python-paramiko 1.7+
# python-lxml 3.0+
# python-libxml2
# python-libxslt
# libxml2
# (Debian) libxslt1-dev
$install \
    python-setuptools python-paramiko python-lxml python-libxml2 \
    python-libxslt1 libxml2 libxslt1-dev
cd "$DIR/ncclient"
sudo python setup.py install

##
## vnfcatalog by iMinds
##
$install \
    python-jinja2

###
### lookbusy, http://www.devin.com/lookbusy/download/lookbusy-1.4.tar.gz
###

cd "$DIR/lookbusy-1.4"
./configure
make
sudo make install
make clean

##
## mininet
##
cd "$DIR/mininet"
sudo python setup.py install

##
## Start the demo automatically
##
mkdir -p ~/bin
cat <<EOF > ~/bin/fbautostart
#!/bin/sh
cd $DIR/gui && xterm -geometry +0+0 &
cd $DIR/gui && sudo ./run &
emacs --no-splash -f tool-bar-mode -g 70x23-0+0 $DIR/walkthrough.org &
EOF
chmod u+x ~/bin/fbautostart

##
## Restore disk space, remove sensitive files, etc.
##
sudo rm -f /etc/udev/rules.d/70-persistent-net.rules
$DIR/mininet/util/install.sh -d
sudo rm -f /tmp/zero
