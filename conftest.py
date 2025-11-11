from hypothesis import Phase, settings

settings.register_profile("pre-push", deadline=None, phases=[Phase.generate])
