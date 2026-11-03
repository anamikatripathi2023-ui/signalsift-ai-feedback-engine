from streamlit.testing.v1 import AppTest


def test_dashboard_renders_without_errors():
    app = AppTest.from_file("../app.py", default_timeout=120).run()
    assert not app.exception
    assert app.title[0].value == "Voice of Customer insights"
    assert len(app.tabs) == 6
