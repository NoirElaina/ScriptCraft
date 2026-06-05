<script setup lang="ts">
import { computed, ref } from 'vue'
import { AlertTriangle, Loader2, LogIn, UserPlus } from '@lucide/vue'

import { login, register, type AuthTokenResponse } from '@/api/auth'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const mode = ref<'login' | 'register'>('login')
const identifier = ref('')
const username = ref('')
const email = ref('')
const password = ref('')
const errorMessage = ref('')
const isSubmitting = ref(false)

const isLoginMode = computed(() => mode.value === 'login')

const emit = defineEmits<{
  authenticated: [result: AuthTokenResponse]
}>()

async function submitAuth() {
  errorMessage.value = ''
  isSubmitting.value = true

  try {
    const result = isLoginMode.value
      ? await login({
          identifier: identifier.value.trim(),
          password: password.value,
        })
      : await register({
          username: username.value.trim(),
          email: email.value.trim(),
          password: password.value,
        })
    emit('authenticated', result)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登录失败'
  } finally {
    isSubmitting.value = false
  }
}

function switchMode(nextMode: 'login' | 'register') {
  mode.value = nextMode
  errorMessage.value = ''
  password.value = ''
}
</script>

<template>
  <Card class="w-full max-w-md">
    <CardHeader>
      <CardTitle>{{ isLoginMode ? '登录 ScriptCraft' : '创建账号' }}</CardTitle>
      <CardDescription>
        {{ isLoginMode ? '打开你的小说改编项目。' : '创建账号后开始保存自己的创作项目。' }}
      </CardDescription>
    </CardHeader>

    <CardContent>
      <form class="space-y-4" @submit.prevent="submitAuth">
        <div v-if="isLoginMode" class="grid gap-2">
          <Label for="auth-identifier">用户名或邮箱</Label>
          <Input id="auth-identifier" v-model="identifier" autocomplete="username" />
        </div>

        <div v-else class="space-y-4">
          <div class="grid gap-2">
            <Label for="auth-username">用户名</Label>
            <Input id="auth-username" v-model="username" autocomplete="username" />
          </div>
          <div class="grid gap-2">
            <Label for="auth-email">邮箱</Label>
            <Input id="auth-email" v-model="email" autocomplete="email" />
          </div>
        </div>

        <div class="grid gap-2">
          <Label for="auth-password">密码</Label>
          <Input
            id="auth-password"
            v-model="password"
            type="password"
            autocomplete="current-password"
          />
        </div>

        <div
          v-if="errorMessage"
          class="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
        >
          <AlertTriangle class="mt-0.5 size-4 shrink-0" />
          <span>{{ errorMessage }}</span>
        </div>

        <Button class="w-full" :disabled="isSubmitting">
          <Loader2 v-if="isSubmitting" class="size-4 animate-spin" />
          <LogIn v-else-if="isLoginMode" class="size-4" />
          <UserPlus v-else class="size-4" />
          {{ isLoginMode ? '登录' : '注册并登录' }}
        </Button>

        <Button
          type="button"
          variant="outline"
          class="w-full"
          @click="switchMode(isLoginMode ? 'register' : 'login')"
        >
          {{ isLoginMode ? '没有账号，去注册' : '已有账号，去登录' }}
        </Button>
      </form>
    </CardContent>
  </Card>
</template>
