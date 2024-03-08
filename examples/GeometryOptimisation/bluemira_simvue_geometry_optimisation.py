# bluemira is an integrated inter-disciplinary design tool for future fusion
# reactors. It incorporates several modules, some of which rely on other
# codes, to carry out a range of typical conceptual fusion reactor design
# activities.
#
# Copyright (C) 2021 M. Coleman, J. Cook, F. Franza, I.A. Maione, S. McIntosh, J. Morris,
#                    D. Short
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
A quick tutorial on the optimisation of geometry in bluemira
"""

import logging

from bluemira.geometry.optimisation import GeometryOptimisationProblem
from bluemira.geometry.parameterisations import PrincetonD
from bluemira.utilities.opt_problems import OptimisationObjective
from bluemira.utilities.optimiser import Optimiser, approx_derivative

from simvue import Handler, Run

# Let's set up a simple GeometryOptimisationProblem, where we minimise the length of
# parameterised geometry.

# First, we set up the GeometryParameterisation, with some bounds on the variables.
x1_lower = 2
x1_value = 2.05
x1_upper = 6
x2_lower = 80
x2_value = 198.5
x2_upper = 260
dz_lower = -0.5
dz_upper = 0.5
max_eval = 500
ftol_abs = 1e-12
ftol_rel = 1e-12

run = Run()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
sth = Handler(run)
logger.addHandler(sth)

run.init(
    metadata={
        "dataset.x1_lower": x1_lower,
        "dataset.x1_upper": x1_upper,
        "dataset.x1_value": x1_value,
        "dataset.x2_lower": x2_lower,
        "dataset.x2_upper": x2_upper,
        "dataset.x2_value": x2_value,
        "dataset.dz_lower": dz_lower,
        "dataset.dz_upper": dz_upper,
        "optimiser.max_eval": max_eval,
        "optimiser.ftol_abs": ftol_abs,
        "optimiser.ftol_rel": ftol_rel,
    },
    description="A simple GeometryOptimisationProblem, where we minimise the length of parameterised geometry using gradient-based optimisation algorithm.",
)

logger.info("Initialised run")
logger.info("Create parameterisation")
parameterisation_1 = PrincetonD(
    {
        "x1": {"lower_bound": x1_lower, "value": x1_value, "upper_bound": x1_upper},
        "x2": {"lower_bound": x2_lower, "value": x2_value, "upper_bound": x2_upper},
        "dz": {"lower_bound": dz_lower, "value": 0, "upper_bound": dz_upper},
    }
)

# Here we're minimising the length, and we can work out that the dz variable will not
# affect the optimisation, so let's just fix at some value and remove it from the problem
parameterisation_1.fix_variable("dz", value=0)

# Now, we set up our optimiser. We'll start with a gradient-based optimisation algorithm
logger.info("Define Optimiser")

slsqp_optimiser = Optimiser(
    "SLSQP",
    opt_conditions={"max_eval": max_eval, "ftol_abs": ftol_abs, "ftol_rel": ftol_rel},
)


# Define the call back function
def calculate_length(vector, parameterisation):
    """
    Calculate the length of the parameterised shape for a given state vector.
    """

    parameterisation.variables.set_values_from_norm(vector)
    print("logging metrics", float(parameterisation.variables["x1"].value))
    run.log_metrics(
        {
            "x1_value": float(parameterisation.variables["x1"].value),
            "x1_lower": float(parameterisation.variables["x1"].lower_bound),
            "x1_upper": float(parameterisation.variables["x1"].upper_bound),
        }
    )
    run.log_metrics(
        {
            "x2_value": float(parameterisation.variables["x2"].value),
            "x2_lower": float(parameterisation.variables["x2"].lower_bound),
            "x2_upper": float(parameterisation.variables["x2"].upper_bound),
        }
    )

    return parameterisation.create_shape().length


def my_minimise_length(vector, grad, parameterisation, ad_args=None):
    """
    Objective function for nlopt optimisation (minimisation) of length.

    Parameters
    ----------
    vector: np.ndarray
        State vector of the array of coil currents.
    grad: np.ndarray
        Local gradient of objective function used by LD NLOPT algorithms.
        Updated in-place.
    ad_args: Dict
        Additional arguments to pass to the `approx_derivative` function.

    Returns
    -------
    fom: Value of objective function (figure of merit).
    """
    ad_args = ad_args if ad_args is not None else {}
    print(vector)
    length = calculate_length(vector, parameterisation)
    if grad.size > 0:
        grad[:] = approx_derivative(
            calculate_length, vector, f0=length, args=(parameterisation,), **ad_args
        )
    run.update_metadata(
        {
            "x1_value": float(parameterisation.variables["x1"].value),
            "x2_value": float(parameterisation.variables["x2"].value),
        }
    )
    return length


# Next, we make our objective function, using in this case one of the ready-made ones.
# NOTE: This `minimise_length` function includes automatic numerical calculation of the
# objective function gradient, and expects a certain signature.
objective = OptimisationObjective(
    my_minimise_length,
    f_objective_args={"parameterisation": parameterisation_1},
)


# Finally, we initialise our `GeometryOptimisationProblem` and run it.
logger.info("Call optimiser")
my_problem = GeometryOptimisationProblem(parameterisation_1, slsqp_optimiser, objective)
my_problem.optimise()


# Here we're minimising the length, within the bounds of our PrincetonD parameterisation,
# so we'd expect that x1 goes to its upper bound, and x2 goes to its lower bound.
run.save("bluemira_simvue_geometry_optimisation.py", "code")
run.close()
