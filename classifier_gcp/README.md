this folder will be for the code in GCP that runs our classifier

- main.py: Flask server
- requirements.txt: dependencies
- Dockerfile: creates the python runtime for our code. I probably need to update this. also not sure what version of python to run but I assume 3.12 is fine.
- saved_liar_vert_model: our model, although the model itself (model.safetensors) it stored separately in a different gcp bucket

- to updload a new model:
`gsutil cp path/to/your_model.pkl gs://pol-disinfo-classifier/`

- to update cloud run code (docker, main.py) from the classifier_gcp directory: 
    `gcloud builds submit --tag gcr.io/cs152-group8-460705/discord-classifier`
- to redeploy cloud run instance from the classifier_gcp directory:
    ```
    gcloud run deploy discord-classifier   --image gcr.io/cs152-group8-460705/discord-classifier   --region=us-central1   --platform=managed   --no-allow-unauthenticated   --service-account=cloudrun-admin@cs152-group8-460705.iam.gserviceaccount.com   --memory=2Gi
  ```