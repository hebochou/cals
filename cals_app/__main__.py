"""Package entry point for `python -m cals_app`."""

from cals_app import create_app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
