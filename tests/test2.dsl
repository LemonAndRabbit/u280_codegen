KERNEL: X_AVG2
COUNT: 6
ITERATE: 3
input x(100, 100)
input z(100, 100)
output y(0, 0) = x(0, -1) * (x(0, 1) + x(0, 0)) + x(0, -2) + x(-1, 0) + z(1, 0)
