from app.services.predictor import Predictor


def test_corrected_inference_version_and_cache_namespace(monkeypatch):
    class Model:
        def predict(self, features):
            return [1.01]

    predictor = Predictor()
    monkeypatch.setattr(predictor, "_model_for", lambda symbol: (Model(), "existing-model-v1"))
    history = [{"close": 100 + i, "volume": 1000 + i} for i in range(12)]
    result = predictor.predict("INFY", history)
    assert result["model"] == "existing-model-v1:latest-bar-v1"
    assert predictor.cache_key("INFY", history).startswith("prediction:latest-bar-v1:")
