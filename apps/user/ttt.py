from django.shortcuts import render,redirect
from django.views.generic import View
import re
from apps.user.models import User
from django.conf import settings
from django.http import HttpResponse
from celery_tasks.tasks import send_register_active_email
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate,login


from django.views.generic import View

class RegisterView(View):
    def get(self,request):
        return render(request,'register.html')

    def post(self,request):
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        if not all([username,password,email]):
            return render(request,'register.html',{'errmsg':'数据不完整'})
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request,'register.html',{'errmsg':'邮箱错误'})
        if allow != 'on':
            return render(request,'register.html',{'errmsg':'用户名已存在'})

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None
        if user:
            return render(request,'register.html',{'errmsg':'用户名重复'})
        # 创建用户 并设置为未激活
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()



        # user = User.objects.create_user(username,email,password)
        # 对信息加密
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info)
        token = token.decode()
        send_register_active_email.delay(email, username, token)
        return redirect(reverse('goods:index'))



