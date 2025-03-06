# bluemira is an integrated inter-disciplinary design tool for future fusion
# reactors. It incorporates several modules, some of which rely on other
# codes, to carry out a range of typical conceptual fusion reactor design
# activities.
#
# Copyright (C) 2021 M. Coleman, J. Cook, F. Franza, I.A. Maione, S. McIntosh,
#                    J. Morris, D. Short
#
# bluemira is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# bluemira is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with bluemira; if not, see <https://www.gnu.org/licenses/>.
"""
Geometry Optimisation

Example taken from: bluemira/examples/optimisation/geometry_optimisation.ex.py

In this example we will go through how to set up a simple geometry
optimisation, including a geometric constraint.

The problem to solve is, minimise the length of our wall boundary,
in the xz-plane, whilst keeping it a minimum distance from our plasma.

We will greatly simplify this problem by working with a circular
plasma, we will use a PrincetonD for the wall shape,
and set the minimum distance to half a meter.
"""

import numpy as np
import os
import sys
from bluemira.display import plot_2d
from bluemira.display.plotter import PlotOptions
from bluemira.geometry.optimisation import optimise_geometry
from bluemira.geometry.parameterisations import GeometryParameterisation, PrincetonD
from bluemira.geometry.tools import distance_to, make_circle
from bluemira.geometry.wire import BluemiraWire

import simvue

def f_objective(geom: GeometryParameterisation) -> float:
    """Objective function to minimise a shape's length."""
    return geom.create_shape().length


def distance_constraint(
    geom: GeometryParameterisation, boundary: BluemiraWire, min_distance: float, run: simvue.Run
) -> float:
    """
    A constraint to keep a minimum distance between two shapes.

    The constraint must be in the form f(x) <= 0, i.e., constraint
    is satisfied if f(x) <= 0.

    Since what we want is 'min_distance <= distance(A, B)', we rewrite
    this in the form 'min_distance - distance(A, B) <= 0', and return
    the left-hand side from this function.
    """
    shape = geom.create_shape()
    # Log all variables as metrics after each iteration, giving human readable names:
    run.log_metrics(
        {
            "inboard_limb_radius": float(geom.variables["x1"].value),
            "outboard_limb_radius": float(geom.variables["x2"].value),
            "vertical_offset": float(geom.variables["dz"].value),
            "length_of_wall": float(shape.length),
            "distance_to_plasma": float(distance_to(shape, boundary)[0])
        }
    )
    return min_distance - distance_to(shape, boundary)[0]

# The original example prints stuff to the console to track progress
# Instead of changing these lines to log events (since we probably want both),
# We can make a class which intercepts stdout and also sends messages to Simvue
class StdoutToSimvue():
    def __init__(self, run: simvue.Run):
        self.run = run
        
    def write(self, message: str):
        # Log the message as an event (so long as it isnt a blank line)
        if message.strip():
            run.log_event(message)
        # And print to console as normal
        sys.__stdout__.write(message)
        
    def flush(self):
        sys.__stdout__.flush()

# Here we will start doing our optimisation. First create a Simvue run,
# using the Run class as a context manager:
with simvue.Run() as run:
    # Initialise our run:
    run.init(
        name="bluemira_geometry_optimisation",
        folder="/simvue_client_demos",
        visibility="tenant" if os.environ.get("CI") else None,
        tags=["bluemira", "simvue_client_examples"],
        description="Minimise the length of a parameterised geometry using gradient-based optimisation algorithm.",
    )
    
    # Redirect stdout so that print statements also get logged as events:
    stdout_sender = StdoutToSimvue(run)
    sys.stdout = stdout_sender

    # Next define the shape of our plasma, and the minimum distance we want between
    # our wall boundary and our plasma:
    min_distance = 0.5
    plasma = make_circle(radius=2, center=(8, 0, 0.25), axis=(0, 1, 0))

    # As with any optimisation, it's important to pick a reasonable initial
    # parameterisation.
    wall_boundary = PrincetonD({
        "x1": {"value": 4, "upper_bound": 6},
        "x2": {"value": 12, "lower_bound": 10},
    })
    
    print("Initial parameterisation:")
    print(wall_boundary.variables)
    print(f"Length of wall    : {wall_boundary.create_shape().length}")
    print(f"Distance to plasma: {distance_to(wall_boundary.create_shape(), plasma)[0]}")
    
    # Create metadata for our original parameters:
    _metadata = {
        var: {
                "initial": wall_boundary.variables[var].value,
                "lower_bound": wall_boundary.variables[var].lower_bound,
                "upper_bound": wall_boundary.variables[var].upper_bound
            }
        for var in ["x1", "x2", "dz"] 
        }
    run.update_metadata({"bluemira_parameters": _metadata})

    # Create and upload an image of the initial design to Simvue
    _plot = plot_2d([wall_boundary.create_shape(), plasma])
    _fig = _plot.get_figure()
    run.save_object(_fig, category="input", name="initial_shape")
    
    # Optimise our geometry using a gradient descent method
    result = optimise_geometry(
        wall_boundary,
        algorithm="SLSQP",
        f_objective=f_objective,
        opt_conditions={"ftol_abs": 1e-6},
        keep_history=True,
        ineq_constraints=[
            {
                "f_constraint": lambda g: distance_constraint(g, plasma, min_distance, run),
                "tolerance": np.array([1e-8]),
            },
        ],
    )

    # Print final results after optimisation
    print("Optimised parameterisation:")
    print(result.geom.variables)

    boundary = result.geom.create_shape()
    print(f"Length of wall    : {boundary.length}")
    print(f"Distance to plasma: {distance_to(boundary, plasma)[0]}")
    
    # Update metadata with final optimised values
    _metadata = {
        var: {
                "final": result.geom.variables[var].value,
            }
        for var in ["x1", "x2", "dz"]
        }
    run.update_metadata({"bluemira_parameters": _metadata})

    # Create and upload an image of the optimised design to Simvue
    _plot = plot_2d([boundary, plasma])
    _fig = _plot.get_figure()
    run.save_object(_fig, category="output", name="final_shape")

    # Use the history to create and upload an image of the design iterations
    geom = PrincetonD()
    ax = plot_2d(plasma, show=False)
    for i, (x, _) in enumerate(result.history):
        geom.variables.set_values_from_norm(x)
        wire = geom.create_shape()
        wire_options = {
            "alpha": 0.5 + ((i + 1) / len(result.history)) / 2,
            "color": "red",
            "linewidth": 0.1,
        }
        ax = plot_2d(wire, options=PlotOptions(wire_options=wire_options), ax=ax, show=False)
    _plot = plot_2d(boundary, ax=ax, show=True)
    _fig = _plot.get_figure()
    run.save_object(_fig, category="output", name="design_iterations")