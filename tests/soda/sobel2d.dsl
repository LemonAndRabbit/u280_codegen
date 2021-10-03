KERNEL: SOBEL2D
COUNT: 15
ITERATE: 1
input img(9720, 1024)
local mag_x = (img(1, -1) - img(-1, -1)) + (img(1,  0) - img(-1,  0)) * 3 + (img(1,  1) - img(-1,  1))
local mag_y = (img(-1, 1) - img(-1, -1)) + (img( 0, 1) - img( 0, -1)) * 3 + (img( 1, 1) - img( 1, -1))
output out(0, 0) = 65535 - (mag_x * mag_x + mag_y * mag_y)
