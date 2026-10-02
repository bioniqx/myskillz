# Speed Test 3: Round budget

You have the systematic-debugging skill. A Python service raises:

```
Traceback (most recent call last):
  File "/srv/app/api/handler.py", line 88, in handle
    return render(order)
  File "/srv/app/render/order.py", line 31, in render
    return TEMPLATE.format(**order)
KeyError: 'shipping_total'
```

`pytest tests/test_render.py::test_order -q` reproduces it every time.

Act. Show every tool call, grouped by message. Then state the total number of model turns
you used before writing the ROOT CAUSE line.
