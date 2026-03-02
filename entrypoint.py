# Root-level stub — actual entrypoint is agents/coordinator/entrypoint.py
# The agentcore toolkit zips the entrypoint's directory, so this file
# is only used if someone runs from the workspace root directly.
from agents.coordinator.entrypoint import app, invoke  # noqa: F401

if __name__ == "__main__":
    app.run()
