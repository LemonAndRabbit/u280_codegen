KERNEL: HOTSPOT
COUNT: 3
ITERATE: 64
BOARDER: streaming
input power(7680, 1024)
input temp(7680, 1024)
local tmp = temp(0,0) + temp(0,0)
local tmp0 = temp(-1,0) + temp(1,0) - tmp
local tmp1 = temp(0,-1) + temp(0,1) - tmp
local tmp2 = 80 - temp(0,0)
local power_center = tmp0*2 + power(0,0)
local power_center = power_center + tmp1*3
local power_center = power_center + tmp2*4
output y(0, 0) = 5*power_center
