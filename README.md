We can use voice recognition to fill forms. 

# Installation 
## Setting Up Your Environment

A simple guide to create an Anaconda environment and install required packages.

### Create and Set Up Environment

```bash
# Create a new conda environment with Python 3.10
conda create -n myenv python=3.10

# Activate the environment
conda activate myenv

# Install packages from requirements.txt
pip install -r requirements.txt
```

### Basic Usage

```bash
# Activate environment when needed
conda activate myenv

# Deactivate when finished
conda deactivate
```

# Execution

```
python server.py
```

Now double click `voice-form.html`

# Future Plans

## Make interaction birectional
For now the interaction is only from user to machine. Next is voice from machine to user in order to give feedback to user. So this eliminate all buttons just saying ok next field will work.

## Fine tune the model for more languages
Support more Indian languages other than English.