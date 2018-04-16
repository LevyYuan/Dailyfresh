from django.shortcuts import render,redirect
from django.views.generic import View
import re
from apps.user.models import User,Address
from django.conf import settings
from django.http import HttpResponse
from celery_tasks.tasks import send_register_active_email
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate,login,logout

from utils.mixin import LoginRequireMixin
from django_redis import get_redis_connection
from apps.goods.models import GoodsSKU


class RegisterView(View):
    # get请求
    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        # 1.接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 2.进行数据校验
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '数据不完整'})
        # 校验邮箱
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})
        # 校验是否同意协议
        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})
        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None
        if user:
            # 用户名已存在
            return render(request, 'register.html', {'errmsg': '用户名已存在'})
        # 3.进行业务处理: 进行用户注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()
        # 发送激活邮件，包含激活链接: http://127.0.0.1:8000/user/active/3
        # 激活链接中需要包含用户的身份信息, 并且要把身份信息进行加密
        # 加密用户的身份信息，生成激活token
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        # 对info加密
        token = serializer.dumps(info)  # bytes
        token = token.decode()
        # 发邮件
        # 这是tasks.py中定义方法 用到了celery
        print(1)
        send_register_active_email.delay(email, username, token)
        print(2)
        # 4.返回应答, 跳转到商品首页
        return redirect(reverse('goods:index'))


class ActiveView(View):
    '''用户激活'''
    def get(self, request, token):
        '''进行用户激活'''
        # 进行解密，获取要激活的用户信息
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            # token的还原
            info = serializer.loads(token)
            # 获取待激活用户的id
            user_id = info['confirm']
            # 根据id获取用户信息
            user = User.objects.get(id=user_id)
            # 将激活标记改为1
            user.is_active = 1
            user.save()
            # 跳转到登录页面
            # 使用反向解析
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            # 激活链接已过期
            # 实际项目需要再给用户发一条邮件，提示激活链接已经过期，这里简单处理
            return HttpResponse('激活链接已过期')


class LoginView(View):
    def get(self, request):
        '''显示登录页面'''
        # 判断是否记住了用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        # 使用模板
        return render(request, 'login.html', {'username':username, 'checked':checked})

    def post(self, request):
        '''登录校验'''
        # 1.接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        # 2.校验数据
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg':'数据不完整'})
        # 用户名授权校验
        user = authenticate(username=username, password=password)
        if user is not None:
            print(3)
            # 用户名密码正确
            if user.is_active:
                print(4)
                # 用户已激活
                # 记录用户的登录状态 内置函数login()
                login(request, user)
                # 设置response为跳转到首页
                print(5)
                next_url = request.GET.get('next', reverse('goods:index'))
                # 跳转到next_url
                response = redirect(next_url) # HttpResponseRedirect
                # 判断是否需要记住用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    # 设置cookie
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    response.delete_cookie('username')
                # 跳转到商品首页
                print(6)
                return response
            else:
                return render(request, 'login.html', {'errmsg':'账户未激活'})
        else:
            return render(request, 'login.html', {'errmsg':'用户名或密码错误'})

# 用户登出
class LogoutView(View):
    def get(self,request):
        logout(request)
        return redirect(reverse('goods:index'))

# 信息页
class UserInfoView(LoginRequireMixin,View):
    def get(self,request):
        # 获取个人信息
        user = request.user
        # 获取收货地址
        try:
            address = Address.objects.get(user=user, is_default=True)
        except Address.objects.model.DoesNotExist:
            # 不存在默认收货地址
            address = None

        # 获取浏览历史记录
        from redis import StrictRedis
        con = get_redis_connection('default')
        history_key = 'history_%d'%user.id

        # 获取用户最新浏览的5个商品的id
        sku_ids = con.lrange(history_key, 0, 4)  # [2,3,1]

        # 从数据库中查询用户浏览的商品的具体信息
        goods_li = GoodsSKU.objects.filter(id__in=sku_ids)

        goods_res = []
        for a_id in sku_ids:
            for goods in goods_li:
                if a_id == goods.id:
                    goods_res.append(goods)

        # 遍历获取用户浏览的商品信息
        goods_li = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_li.append(goods)

        # 组织上下文
        context = {'page': 'user',
                   'address': address,
                    'goods_li':goods_li}
        # 除了你给模板文件传递的模板变量之外，django框架会把request.user也传给模板文件
        return render(request, 'user_center_info.html', context)


# 订单页
class UserOrderView(LoginRequireMixin,View):
    def get(self,request):
        print(111)
        return render(request,'user_center_order.html',{'page':'order'})


# 地址页
class AddressView(LoginRequireMixin,View):
    def get(self,request):
        # 获取User对象
        print(222)
        user = request.user
        # 使用模型管理器
        address = Address.objects.get_default_address(user)
        return render(request,'user_center_site.html',{'page':'address','address':address})

    def post(self,request):
        # 1.接收数据
        receiver = request.POST.get('receiver')
        addr  = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')
        print(receiver)
        print(addr)
        print(zip_code)
        print(phone)
        # 2.校验数据
        # 完整性
        if not all([receiver,addr,phone]):
            return render(request,'user_center_site.html',{'errmsg':'数据不完整'})
        # 校验手机号
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$', phone):
            return render(request, 'user_center_site.html', {'errmsg': '手机号格式错误'})
        # 3.添加地址
        user = request.user
        # 展示默认收货地址(此处改为自定义查询集)
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     address = None

        # 使用模型管理器
        address = Address.objects.get_default_address(user)
        if address:
            is_default = False
        else:
            is_default = True
        # 添加地址
        print(555)
        Address.objects.create(user = user,
                               receiver = receiver,
                               addr = addr,
                               zip_code = zip_code,
                               phone = phone,
                               is_default = is_default)
        # 返回应答
        return redirect(reverse('user:address'))
