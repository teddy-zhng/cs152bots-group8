import requests

# Local Flask API endpoint
API_URL = "http://127.0.0.1:5000/classify"


test_examples = [
    # Factually correct
    {
        "message": "The Earth revolves around the Sun.",
        "justification": "This is established scientific consensus."
    },
    {
        "message": "Barack Obama was born in Hawaii.",
        "justification": "Official records confirm this."
    },

    #  Obvious misinformation
    {
        "message": "Vaccines contain microchips for government tracking.",
        "justification": "A common conspiracy theory widely debunked by health agencies."
    },
    {
        "message": "Drinking bleach cures COVID-19.",
        "justification": "A dangerous and false claim that has been widely condemned."
    },

    # Borderline or controversial
    {
        "message": "The election was rigged based on mail-in ballots.",
        "justification": "A disputed claim promoted by some partisan sources."
    },
    {
        "message": "5G towers contributed to the spread of COVID-19.",
        "justification": "A viral theory without credible scientific backing."
    },

    # Fact with no justification
    {
        "message": "Water boils at 100 degrees Celsius at sea level."
    },

    # Misinformation with no justification
    {
        "message": "Climate change is a hoax created by scientists."
    },

    # Vague claim
    {
        "message": "Most politicians lie all the time.",
        "justification": "An opinionated generalization often found in online discourse."
    },

    # Statistical fact
    {
        "message": "The unemployment rate in the U.S. was 3.4% in January 2023.",
        "justification": "According to U.S. Bureau of Labor Statistics reports."
    }
]

# Send requests to API
for i, example in enumerate(test_examples, 1):
    print(f"\n Example {i}:")
    print(f"Message: {example['message']}")
    if "justification" in example:
        print(f"Justification: {example['justification']}")
    else:
        print("Justification: (none)")

    try:
        response = requests.post(API_URL, json=example)
        if response.status_code == 200:
            result = response.json()
            print(f"Prediction: {result['classification']}")
            print(f"Confidence: {result['confidence_score']}")
        else:
            print(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")
