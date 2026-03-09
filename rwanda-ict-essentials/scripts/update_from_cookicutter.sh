#!/usr/bin/env bash
set -e

if [ -d tmp_cookie ]; then
  echo "Cleaning up"
  rm -rf tmp_cookie
fi

echo "Running cookiecutter"
cookiecutter --no-input 'gh:learningequality/cookiecutter-chef' \
  -v \
  -f \
  chef_template="Sous Chef" \
  project_slug="tmp_cookie"

echo "Copying useful files from upstream"
cp tmp_cookie/README.md ./
cp tmp_cookie/requirements.txt ./
cp tmp_cookie/Quickstart.ipynb ./
cp tmp_cookie/utils/* ./utils/
cp -r tmp_cookie/examples/* ./examples/

echo "Cleaning up"
rm -rf tmp_cookie