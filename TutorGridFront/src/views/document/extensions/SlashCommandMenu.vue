<template>
  <Teleport to="body">
    <v-card
      v-if="open"
      class="slash-menu"
      elevation="6"
      rounded="lg"
      :style="popupStyle"
    >
      <v-list density="compact" nav class="py-1">
        <v-list-item
          v-for="(item, i) in filtered"
          :key="item.command"
          :active="i === activeIndex"
          rounded="md"
          class="slash-menu__item"
          @mouseenter="$emit('hover', i)"
          @click="$emit('select', item)"
        >
          <template #prepend>
            <v-icon :icon="item.icon" :color="item.color || 'primary'" size="20" />
          </template>
          <v-list-item-title class="text-body-2 font-weight-medium">
            {{ item.title }}
          </v-list-item-title>
          <v-list-item-subtitle class="text-caption">
            {{ item.subtitle }}
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item
          v-if="filtered.length === 0"
          disabled
          class="slash-menu__item"
        >
          <v-list-item-title class="text-caption text-medium-emphasis">
            无匹配命令
          </v-list-item-title>
        </v-list-item>
      </v-list>
    </v-card>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { filterSlashItems } from "./slash-command-items";

export interface SlashItem {
  command: string;
  title: string;
  subtitle: string;
  icon: string;
  color?: string;
  keywords?: string[];
}

const props = defineProps<{
  open: boolean;
  top: number;
  left: number;
  query: string;
  items: SlashItem[];
  activeIndex: number;
}>();

defineEmits<{
  (e: "select", item: SlashItem): void;
  (e: "hover", index: number): void;
}>();

const filtered = computed(() => filterSlashItems(props.items, props.query));

const popupStyle = computed(() => ({
  top: `${props.top}px`,
  left: `${props.left}px`,
}));

defineExpose({ filtered });
</script>

<style scoped lang="scss">
.slash-menu {
  position: fixed;
  z-index: 2400;
  width: 280px;
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.slash-menu__item {
  min-height: 44px;
}
</style>
