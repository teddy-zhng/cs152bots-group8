this folder will be for the code in GCP that runs our classifier

- main.py: Flask server
- requirements.txt: dependencies
- Dockerfile: creates the python runtime for our code. I probably need to update this. also not sure what version of python to run but I assume 3.12 is fine.
- saved_liar_vert_model: our model, although the model itself (model.safetensors) it stored separately in a different gcp bucket

```