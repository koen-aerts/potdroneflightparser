# potdroneflightparser
Parser to read drone flight data from Potensic bin files

This project is based on reverse engineering of the Potensic flight bin files and by trial and error. Only some of the most basic metrics are pulled from this proprietary file format, most of it is still a mystery to me.

# How to run
```sh
python3 extractFlightData.py ./20230401-Atom\ SE-Drone.zip > 20230401.csv
```