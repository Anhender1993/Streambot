from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

# Path to your streamers.json
STREAMERS_FILE = "streamers.json"

# Helper to load streamers
def load_streamers():
    if not os.path.exists(STREAMERS_FILE):
        return []
    with open(STREAMERS_FILE, "r") as f:
        return json.load(f)

# Helper to save streamers
def save_streamers(streamers):
    with open(STREAMERS_FILE, "w") as f:
        json.dump(streamers, f, indent=4)

# Home page - list all streamers
@app.route("/")
def home():
    streamers = load_streamers()
    return jsonify({
        "tracked_streamers": streamers,
        "instructions": {
            "add": "/addstreamer/<twitch_username>",
            "remove": "/removestreamer/<twitch_username>"
        }
    })

# Add a streamer
@app.route("/addstreamer/<streamer_name>", methods=["GET"])
def add_streamer(streamer_name):
    streamers = load_streamers()
    if streamer_name.lower() in [s.lower() for s in streamers]:
        return jsonify({"message": f"{streamer_name} is already being tracked."}), 400

    streamers.append(streamer_name)
    save_streamers(streamers)
    return jsonify({"message": f"✅ Added {streamer_name} to the watch list!"})

# Remove a streamer
@app.route("/removestreamer/<streamer_name>", methods=["GET"])
def remove_streamer(streamer_name):
    streamers = load_streamers()
    updated_streamers = [s for s in streamers if s.lower() != streamer_name.lower()]

    if len(updated_streamers) == len(streamers):
        return jsonify({"message": f"{streamer_name} was not found in the list."}), 404

    save_streamers(updated_streamers)
    return jsonify({"message": f"✅ Removed {streamer_name} from the watch list."})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
