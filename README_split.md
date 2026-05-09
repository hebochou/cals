## Student Split Summary

This document summarizes the `student.py` and `logic.py` modular split.

### Directory Tree

```text
cals_app/
  routes/
    student/
      __init__.py
      blueprint.py
      common.py
      favorites.py
      health.py
      home.py
      mistakes.py
      practice.py
      practice_api.py
      question_bank.py
      test_student.py
  services/
    student/
      __init__.py
      accounts.py
      analytics.py
      attempts.py
      evaluation.py
      favorites.py
      mistakes.py
      questions.py
      recommendations.py
      test_logic.py
```

### Added Files

- `cals_app/routes/student/blueprint.py`: shared `student_bp` and compile cache.
- `cals_app/routes/student/common.py`: pagination, filter, and list-loading helpers.
- `cals_app/routes/student/home.py`: home page and stats API.
- `cals_app/routes/student/question_bank.py`: question list/detail routes.
- `cals_app/routes/student/favorites.py`: favorite page and toggle route.
- `cals_app/routes/student/practice.py`: practice page and sample-run route.
- `cals_app/routes/student/practice_api.py`: chapter/recommend compile and submit APIs.
- `cals_app/routes/student/mistakes.py`: mistake-book list/remove routes.
- `cals_app/routes/student/health.py`: DB health endpoint.
- `cals_app/services/student/accounts.py`: user bootstrap and password helpers.
- `cals_app/services/student/favorites.py`: favorite persistence helpers.
- `cals_app/services/student/questions.py`: question repository and tag helpers.
- `cals_app/services/student/attempts.py`: attempt log helpers.
- `cals_app/services/student/mistakes.py`: mistake log helpers.
- `cals_app/services/student/recommendations.py`: recommendation scoring logic.
- `cals_app/services/student/evaluation.py`: coding-question evaluation helper.
- `cals_app/services/student/analytics.py`: admin stats helpers reused from legacy logic.

### Compatibility Notes

- `cals_app.services.logic` remains as a compatibility facade that re-exports the split services.
- `cals_app.routes.student` now resolves to the package directory, so the import path used by `create_app()` stays unchanged.
- Existing endpoint URLs and blueprint name `student_bp` are preserved.
