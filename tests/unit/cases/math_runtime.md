$ runtime = a + b n $

where $a$ is the intercept of the line and $b$ is the slope.

On the other hand, if `add` is linear, the total time for $n$ adds would be quadratic. If we plot runtime versus problem size, we expect to see a parabola. Or mathematically, something like:

$ runtime = a + b n + c n^2 $

With perfect data, we might be able to tell the difference between a straight line and a parabola, but if the measurements are noisy, it can be hard to tell. A better way to interpret noisy measurements is to plot runtime and problem size on a **log-log** scale.