from django.contrib import admin

# Register your models here.

from apps.goods.models import *

admin.site.register(GoodsImage)
admin.site.register(GoodsType)
admin.site.register(GoodsSKU)
admin.site.register(Goods)
admin.site.register(IndexGoodsBanner)
admin.site.register(IndexPromotionBanner)
admin.site.register(IndexTypeGoodsBanner)