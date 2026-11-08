"""The wall-time budget of the parallel read fan-out (story 1.6, log I2-35).

A pure constant: it sets how long one turn may wait for its independent reads. It is not a time
rule of the domain and it reads no clock. The 800 ms k6 threshold leaves the rest of the turn
(the single writer queue, prose and the audit transaction) the remaining room.
"""

DEFAULT_FANOUT_BUDGET_SECONDS = 0.5
