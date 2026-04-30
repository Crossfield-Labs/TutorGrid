/**
 * main.js
 *
 */

// Components
import App from "./App.vue";

// Composables
import { createApp } from "vue";
import vuetify from "./plugins/vuetify";
import piniaPersist from "pinia-plugin-persist";
import "@/styles/main.scss";
import router from "./router";
import i18n from "./plugins/i18n";

const pinia = createPinia();
pinia.use(piniaPersist);
const app = createApp(App);

app.use(router);
app.use(pinia);
app.use(i18n);
app.use(vuetify);
app.mount("#app");
