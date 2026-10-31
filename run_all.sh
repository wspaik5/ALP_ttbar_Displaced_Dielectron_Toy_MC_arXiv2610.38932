#!/usr/bin/env bash
# Reproduce all four figures (about 1 minute on a laptop).
set -e
mkdir -p figures
python3 plot_efficiency.py  | tee figures/fig1_numbers.txt
python3 plot_bfield.py      | tee figures/fig2_numbers.txt
python3 plot_conversions.py | tee figures/fig3_numbers.txt
python3 plot_vertex.py    | tee figures/fig4_numbers.txt
