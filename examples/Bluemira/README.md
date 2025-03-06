# Geometry optimisation using Bluemira

[Bluemira](https://github.com/Fusion-Power-Plant-Framework/bluemira) is an integrated inter-disciplinary design tool for future fusion reactors. It incorporates several modules, some of which rely on other codes, to carry out a range of typical conceptual fusion reactor design activities. This example uses Simvue to track the optimisation of the geometry of a Princeton-D shaped magnet, while maintaining a safe minimum distance to the plasma of 0.5m.


To run this example, you will need to install Bluemira. For details of installation of Bluemira please refer to https://bluemira.readthedocs.io/en/develop/installation.html

Once you have Bluemira installed and are running the `bluemita` conda environment (or similar), install Simvue with the plotting extras:
```
pip install simvue[plot]
```
Then move into the example's directory:
```
cd examples/Bluemira
```
Make a simvue.toml file - click Create New Run on the web UI, copy the contents listed, and paste into a config file.

Finally, run the example:
```
python geometry_optimisation.py
```
