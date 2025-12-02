# Example Notebooks
These example notebooks give you some simple examples of integrating Simvue into your workflow to track and monitor any simulation or data processing task.

## Basic Example

[![Open In Collab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1VleQ-Ga010w9TE2oTBnTnJdGHlWZMJKn?usp=sharing)

In this example we take a simple piece of Python code which finds the average of a set of random numbers, and use Simvue to:

* Start a new run to track the progress of the code
* Upload metrics in real time to the server
* Upload events to tell us when the code is complete

## Detailed Example

[![Open In Collab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1GHItQvWS9HBUoTmdZxDYnGq0wfmdYhsc?usp=sharing)

In this more detailed example, we create a simple simulation of customers arriving at a bank counter and either being served or running out of patience and leaving. We then use Simvue to:

* Start a new run to track the progress of this simulation
* Upload artifacts for storage in the form of a file and a Numpy array
* Add metadata to keep track of input parameters for the simulation
* Upload metrics in real time to the server to keep track of the average customer wait time and percentage who don't get served
* Add events which show us the status of each customer
* Add alerts which notify us if too many customers are not being served in time

## Non-Python Example

[![Open In Collab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1fDlJ6xeRmHfDsdqN5ATJ8lTj4lqavTqd?usp=sharing)

In this example, we demonstrate how Simvue can be used to track simulations (or other computational tasks) which are not Python-based by tracking the output and/or log files which they create during execution. We use Simvue to:
* Create a class which wraps the Run class, adding functionality for tracking output files in real time using Multiparser
* Use this class to start a new run to track the progress of this simulation
* Use `add_process` to have Simvue start and monitor a non-Python simulation
* Upload metrics in real time to the server to keep track of the temperature of a sample being heated and cooled
* Upload the script and output files as artifacts for storage on the Simvue server