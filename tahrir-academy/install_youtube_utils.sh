#!/usr/bin/env bash

echo "Installing latest nataren/youtube_utils..."
if [ ! -d youtube_utils ]; then
  git clone git@github.com:nataren/youtube_utils.git
fi

cd youtube_utils
git fetch origin
git checkout master
git reset --hard origin/master

pip install -U -r requirements.txt

touch __init__.py


