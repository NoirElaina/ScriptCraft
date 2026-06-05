<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown, Clock, LogOut, Loader2, UserRound } from '@lucide/vue'

import type { AuthUser } from '@/api/auth'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { formatTime } from '@/lib/workspace-formatters'

const props = defineProps<{
  user: AuthUser
  isLoggingOut: boolean
}>()

const emit = defineEmits<{
  showRuns: []
  logout: []
}>()

const isUserCenterOpen = ref(false)

const avatarText = computed(() => {
  return props.user.username.trim().slice(0, 1).toUpperCase() || 'U'
})
</script>

<template>
  <Dialog v-model:open="isUserCenterOpen">
    <DropdownMenu>
      <DropdownMenuTrigger as-child>
        <Button variant="outline" class="h-9 gap-2 rounded-full px-2 pr-3">
          <Avatar size="sm">
            <AvatarFallback class="bg-foreground text-background">
              {{ avatarText }}
            </AvatarFallback>
          </Avatar>
          <span class="hidden max-w-28 truncate text-sm font-medium sm:inline">
            {{ user.username }}
          </span>
          <ChevronDown class="size-3.5 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" class="w-64">
        <DropdownMenuLabel>
          <div class="flex items-center gap-3">
            <Avatar>
              <AvatarFallback class="bg-foreground text-background">
                {{ avatarText }}
              </AvatarFallback>
            </Avatar>
            <div class="min-w-0">
              <p class="truncate text-sm font-medium">{{ user.username }}</p>
              <p class="truncate text-xs font-normal text-muted-foreground">{{ user.email }}</p>
            </div>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem @click="isUserCenterOpen = true">
          <UserRound class="size-4" />
          用户中心
        </DropdownMenuItem>
        <DropdownMenuItem @click="emit('showRuns')">
          <Clock class="size-4" />
          AI 运行记录
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          variant="destructive"
          :disabled="isLoggingOut"
          @click="emit('logout')"
        >
          <Loader2 v-if="isLoggingOut" class="size-4 animate-spin" />
          <LogOut v-else class="size-4" />
          退出登录
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>

    <DialogContent class="sm:max-w-[420px]">
      <DialogHeader>
        <DialogTitle>用户中心</DialogTitle>
        <DialogDescription>当前登录账号信息。</DialogDescription>
      </DialogHeader>

      <div class="space-y-3 text-sm">
        <div class="flex items-center gap-3 rounded-lg border p-3">
          <Avatar>
            <AvatarFallback class="bg-foreground text-background">
              {{ avatarText }}
            </AvatarFallback>
          </Avatar>
          <div class="min-w-0">
            <p class="truncate font-medium">{{ user.username }}</p>
            <p class="truncate text-muted-foreground">{{ user.email }}</p>
          </div>
        </div>

        <div class="grid gap-2 rounded-lg bg-muted/60 p-3">
          <div class="flex items-center justify-between gap-4">
            <span class="text-muted-foreground">用户 ID</span>
            <span class="font-medium">{{ user.id }}</span>
          </div>
          <div class="flex items-center justify-between gap-4">
            <span class="text-muted-foreground">注册时间</span>
            <span class="text-right font-medium">{{ formatTime(user.created_at) }}</span>
          </div>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
