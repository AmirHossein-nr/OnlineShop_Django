import json

import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect

from cart.cart_sessions import Cart
from orders.models import Order, OrderItem


@login_required
def create_order(request):
    cart = Cart(request)
    order = Order.objects.create(user=request.user)
    for item in cart:
        OrderItem.objects.create(order=order, product=item['product'], price=item['price'],
                                 quantity=item['quantity'])
    cart.clear()
    return redirect('orders:detail', order.id)


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'orders/order.html', {'order': order})


MERCHANT = 'XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX'  # Merchant ID
ZP_API_REQUEST = "https://api.zarinpal.com/pg/v4/payment/request.json"
ZP_API_VERIFY = "https://api.zarinpal.com/pg/v4/payment/verify.json"
ZP_API_STARTPAY = "https://www.zarinpal.com/pg/StartPay/{authority}"
description = "توضیحات مربوط به تراکنش را در این قسمت وارد کنید"  # Required
mobile = '09123456789'  # Optional
# Important: need to edit for real server.
CallbackURL = 'http://localhost:8000/orders/verify/'


@login_required
def payment(request, order_id, price):
    global amount, o_id  # Rials / Required
    amount = price
    o_id = order_id
    req_data = {
        "merchant_id": MERCHANT,
        "amount": amount,
        "callback_url": CallbackURL,
        "description": description,
        "metadata": {"mobile": mobile, "email": request.user.email}
    }
    req_header = {"accept": "application/json",
                  "content-type": "application/json'"}
    req = requests.post(url=ZP_API_REQUEST, data=json.dumps(
        req_data), headers=req_header)
    authority = req.json()['data']['authority']
    if len(req.json()['errors']) == 0:
        return redirect(ZP_API_STARTPAY.format(authority=authority))
    else:
        e_code = req.json()['errors']['code']
        e_message = req.json()['errors']['message']
        return HttpResponse(f"Error code: {e_code}, Error Message: {e_message}")


@login_required
def verify(request):
    order = get_object_or_404(Order, id=o_id)
    t_status = request.GET.get('Status')
    t_authority = request.GET['Authority']
    if request.GET.get('Status') == 'OK':
        req_header = {"accept": "application/json",
                      "content-type": "application/json'"}
        req_data = {
            "merchant_id": MERCHANT,
            "amount": amount,
            "authority": t_authority
        }
        req = requests.post(url=ZP_API_VERIFY, data=json.dumps(req_data), headers=req_header)
        if len(req.json()['errors']) == 0:
            t_status = req.json()['data']['code']
            if t_status == 100:
                order.is_paid = True
                order.save()
                messages.success(request, 'Transaction success.\nRefID: ' + str(
                    req.json()['data']['ref_id']
                ), 'success')
                return redirect('shop:home')
            elif t_status == 101:
                return HttpResponse('Transaction submitted : ' + str(
                    req.json()['data']['message']
                ))
            else:
                return HttpResponse('Transaction failed.\nStatus: ' + str(
                    req.json()['data']['message']
                ))
        else:
            e_code = req.json()['errors']['code']
            e_message = req.json()['errors']['message']
            return HttpResponse(f"Error code: {e_code}, Error Message: {e_message}")
    else:
        return HttpResponse('Transaction failed or canceled by user')
