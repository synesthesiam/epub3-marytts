#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"
venv="${this_dir}/.venv"

if [[ -d "${venv}" ]]; then
    rm -rf "${venv}"
fi

python3 -m venv "${venv}"
source "${venv}/bin/activate"

pip3 install wheel
pip3 install -r "${this_dir}/requirements.txt"
