INITIAL_LOW = 0
INITIAL_HIGH = pow(2, 32) - 1


QUARTER = (INITIAL_HIGH - INITIAL_LOW + 1) // 4
HALF = (INITIAL_HIGH - INITIAL_LOW + 1) // 2
THREE_QUARTER = 3 * QUARTER
MASK = 0xFFFFFFFF


def compute_cumulative_ranges(freq):
    cum_low = [0] * 257
    cum_high = [0] * 257
    curr_low = 0

    for i in range(257):
        cum_low[i] = curr_low
        cum_high[i] = curr_low + freq[i]
        curr_low = cum_high[i]

    return cum_low, cum_high
