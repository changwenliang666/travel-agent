<template>
  <article class="days" v-if="plan && plan.days && plan.days.length">
    <section class="day" v-for="day in plan.days" :key="day.day">
      <h3>第 {{ day.day }} 天 · {{ day.title }}</h3>
      <div class="weather" v-if="day.weather">{{ day.weather }}</div>
      <div v-for="(item, index) in day.items" :key="index">{{ item.time }} {{ item.name }} · {{ item.note }}</div>
    </section>
    <div v-if="plan.sources && plan.sources.length">
      <div v-for="source in plan.sources" :key="source.url">
        <a :href="source.url" target="_blank">{{ source.title }}</a>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import type { Plan } from '../api'
defineProps<{ plan: Plan | null }>()
</script>
