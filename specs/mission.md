# Mission

Tremor log is a portfolio project. It shows that a published and validated Parkinson's tremor detector can run on a watch by itself, with a face designed for a person who has tremor.

The design target is a person with Parkinson's who wears the watch on the more affected wrist. Most such people are over sixty, their hands shake, their movements can freeze, and their contrast and colour vision is weaker. The builder wears the watch for the tests and the recorded demo. Reviewers read the repo and the reports.

The watch reads its gyroscope at about 114 readings a second and converts the readings to 100 a second. Every second it runs a C port of the ParaDigMa 1.1.2 tremor detector on the last 4 seconds. The face shows Tremor, Rest, Arm moving, Waiting, or Dose due, and it keeps the session's share of still time with tremor. The watch also reminds the wearer of dose times and lets them log a dose with one tap. When a laptop is plugged in over USB, the watch writes every reading and every answer to it as text, so each window can be checked against the Python toolbox afterwards.

The project uses the detector as published and never retrains it. The detector undercounts by design. The setup is tested on public recordings and on the builder's own wrist, and never on a person with tremor. A one to two hour session shows how the measure works, but it does not validate it, and the project gives no basis for dose decisions.

The full build spec is context/tremor-log-plan.html. Where that page and these files differ, that page wins.
