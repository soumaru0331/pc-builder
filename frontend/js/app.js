const API = "";  // same origin

const { createApp, ref, computed, reactive, onMounted, watch } = Vue;

createApp({
  setup() {
    // ── View ────────────────────────────────────────────────────────────
    const view = ref("home");

    // ── Stats ───────────────────────────────────────────────────────────
    const stats = reactive({ parts: 0, builds: 0, brands: 0 });
    const recentBuilds = ref([]);

    // ── Categories ──────────────────────────────────────────────────────
    const categories = [
      { key: "cpu",         label: "CPU",          icon: "🔲" },
      { key: "motherboard", label: "マザーボード",  icon: "🖨️" },
      { key: "memory",      label: "メモリ",         icon: "💾" },
      { key: "gpu",         label: "GPU",           icon: "🎮" },
      { key: "storage",     label: "ストレージ",     icon: "💿" },
      { key: "psu",         label: "電源",           icon: "🔌" },
      { key: "case",        label: "ケース",          icon: "📦" },
      { key: "cooler",      label: "CPUクーラー",    icon: "❄️" },
    ];

    const featuresCfg = [
      { icon: "🔍", title: "互換性チェック", desc: "ソケット・DDR世代・フォームファクター・TDP・電力を自動検証" },
      { icon: "💴", title: "リアタイ最安値", desc: "価格.com・Amazon・メルカリ・ヤフオクを横断検索" },
      { icon: "💡", title: "AIサジェスト",  desc: "予算と用途から3パターンの最適構成を自動提案" },
      { icon: "🏷️", title: "セール検知",   desc: "参考価格と比較して特価・セールを自動検出" },
      { icon: "📊", title: "Excel出力",    desc: "構成・互換性・価格比較を整形されたExcelで出力" },
      { icon: "📄", title: "PDF出力",     desc: "印刷対応のきれいな構成レポートをPDFで出力" },
    ];
    const features = featuresCfg;

    // ── Mobile Menu ─────────────────────────────────────────────────────
    const mobileMenuOpen = ref(false);

    // ── Admin Auth ───────────────────────────────────────────────────────
    let _adminPassword = "";
    const adminModal = reactive({
      show: false, input: "", error: "",
      resolve: null, reject: null,
    });
    function adminHeaders() {
      return _adminPassword ? { "Content-Type": "application/json", "X-Admin-Password": _adminPassword } : { "Content-Type": "application/json" };
    }
    function requireAdmin() {
      if (_adminPassword) return Promise.resolve(_adminPassword);
      return new Promise((resolve, reject) => {
        adminModal.input = "";
        adminModal.error = "";
        adminModal.resolve = resolve;
        adminModal.reject = reject;
        adminModal.show = true;
      });
    }
    async function confirmAdminPassword() {
      if (!adminModal.input) { adminModal.error = "パスワードを入力してください"; return; }
      // テスト認証: /api/sync/history を叩いてみる (認証不要エンドポイント)
      // ここではパスワードを一時保存して呼び出し元に解決を返す
      _adminPassword = adminModal.input;
      adminModal.show = false;
      adminModal.error = "";
      if (adminModal.resolve) {
        adminModal.resolve(_adminPassword);
        adminModal.resolve = null;
        adminModal.reject = null;
      }
    }

    // ── Builder State ────────────────────────────────────────────────────
    const currentBuild  = reactive({ id: null, name: "新しい構成", purpose: "gaming" });
    const selectedCat   = ref("cpu");
    const selectedParts = reactive({});   // { category: partObj }
    const customPrices  = reactive({});   // { category: { price, is_used } }
    const allParts      = ref([]);
    const filteredParts = ref([]);
    const loadingParts  = ref(false);
    const searchQ       = ref("");
    const sortBy        = ref("score");
    const genFilter     = ref("");   // CPU 世代フィルター
    const memCapFilter  = ref("");   // メモリ容量フィルター
    // カテゴリ別フィルター
    const catFilters = reactive({
      gpu_series: "", gpu_vram: "",
      mb_socket: "", mb_form: "", mb_chipset: "", mb_wifi: "", mb_usbc: "",
      sto_type: "", sto_cap: "",
      psu_watt: "",
      case_form: "",
      cooler_type: "", cooler_airflow: "", cooler_lcd: "",
      color: "",          // 全カテゴリ共通カラーフィルター
    });
    const memGenFilter = ref("");  // DDR4 / DDR5
    const maxScore      = computed(() => Math.max(...allParts.value.map(p => p.benchmark_score || 0), 1));

    // ── Part Price Cache ─────────────────────────────────────────────────
    // { partId: { price, is_used, loading } }
    const partPriceCache = reactive({});
    let priceFetchController = null;

    async function fetchVisiblePrices() {
      // 前の取得をキャンセル
      if (priceFetchController) priceFetchController.cancelled = true;
      const ctrl = { cancelled: false };
      priceFetchController = ctrl;

      const targets = filteredParts.value.slice(0, 20); // 上位20件
      for (const part of targets) {
        if (ctrl.cancelled) return;
        if (partPriceCache[part.id]) continue; // 取得済みはスキップ
        partPriceCache[part.id] = { loading: true };
        try {
          const res = await apiFetch(`/api/prices/${part.id}`);
          if (ctrl.cancelled) return;
          const cheapest = res.cheapest_new || res.cheapest_used;
          if (cheapest) {
            partPriceCache[part.id] = {
              price: cheapest.price,
              is_used: !res.cheapest_new && !!res.cheapest_used,
              loading: false,
            };
          } else {
            partPriceCache[part.id] = { price: null, loading: false };
          }
        } catch (e) {
          if (!ctrl.cancelled) partPriceCache[part.id] = { price: null, loading: false };
        }
      }
    }

    function getDisplayPrice(part) {
      const cached = partPriceCache[part.id];
      if (!cached || cached.loading) return null;           // null = まだ不明
      return cached.price ?? part.reference_price;
    }
    function isPriceLoading(part) {
      return !!partPriceCache[part.id]?.loading;
    }
    function isPriceUsed(part) {
      return !!partPriceCache[part.id]?.is_used;
    }

    // Compat
    const compatIssues  = ref([]);
    const compatLoading = ref(false);

    // ── Power ────────────────────────────────────────────────────────────
    const totalTdp = computed(() => {
      let t = 0;
      for (const p of Object.values(selectedParts)) {
        t += (p.tdp || 0);
      }
      return t;
    });
    const psuWattage = computed(() => {
      const psu = selectedParts["psu"];
      return psu ? (psu.specs?.wattage || 0) : 0;
    });
    const powerPercent = computed(() => {
      if (!psuWattage.value) return 0;
      return Math.min(100, Math.round(totalTdp.value / psuWattage.value * 100));
    });
    const powerColor = computed(() => {
      if (powerPercent.value > 85) return "#E74C3C";
      if (powerPercent.value > 70) return "#F39C12";
      return "#27AE60";
    });

    // ── Total Price ──────────────────────────────────────────────────────
    const totalPrice = computed(() => {
      let t = 0;
      for (const [cat, part] of Object.entries(selectedParts)) {
        const cp = customPrices[cat];
        t += cp ? cp.price : (part.reference_price || 0);
      }
      return t;
    });

    // ── Helpers ──────────────────────────────────────────────────────────
    function getCatIcon(key) {
      return categories.find(c => c.key === key)?.icon || "📦";
    }
    function getCatLabel(key) {
      return categories.find(c => c.key === key)?.label || key;
    }
    function getSelectedPart(cat) {
      return selectedParts[cat] || null;
    }
    function catHasError(cat) {
      return compatIssues.value.some(i => i.level === "error" && i.category?.includes(cat));
    }
    function getEffectivePrice(part) {
      const cp = customPrices[part.category];
      return cp ? cp.price : (part.reference_price || 0);
    }
    function getPartSubtext(part) {
      const s = part.specs || {};
      if (part.category === "cpu")
        return `${s.socket || ""} · ${s.cores || ""}コア · ${s.memory_type?.join("/")||""}`;
      if (part.category === "gpu")
        return `VRAM ${s.vram||"?"}GB · PCIe ${s.pcie_version||""} · ${s.length||"?"}mm`;
      if (part.category === "motherboard") {
        const wifiStr = s.wifi ? ` · ${s.wifi}` : "";
        const usbcStr = s.usb_c_rear > 0 ? ` · USB-C×${s.usb_c_rear}` : "";
        const tbStr   = s.thunderbolt ? " · TB4" : "";
        const m2Str   = s.m2_slots ? ` · M.2×${s.m2_slots}` : "";
        const slotStr = s.memory_slots ? ` · DIMMスロット×${s.memory_slots}` : "";
        return `${s.socket||""} · ${s.chipset||""} · ${s.form_factor||""}${wifiStr}${usbcStr}${tbStr}${m2Str}${slotStr}`;
      }
      if (part.category === "memory") {
        const total = (s.capacity||0) * (s.modules||1);
        return `${s.memory_type||""} ${s.speed||""}MHz · 1枚${s.capacity||"?"}GB × ${s.modules||1} = 合計${total}GB`;
      }
      if (part.category === "storage")
        return `${s.type||""} · ${s.interface||""} · ${s.capacity||"?"}GB`;
      if (part.category === "psu")
        return `${s.wattage||"?"}W · ${s.efficiency||""} · ${s.modular||""}モジュラー`;
      if (part.category === "case")
        return `${(s.form_factors||[]).join("/")} · GPU ${s.max_gpu_length||"?"}mm`;
      if (part.category === "cooler") {
        if (s.type === "AIO") {
          const lcd = s.lcd_display ? " · LCDあり" : "";
          return `簡易水冷 ${s.aio_size||"?"}mm · 最大${s.max_tdp||"?"}W${lcd}`;
        } else {
          const style = s.airflow_direction === "top_flow" ? "トップフロー" : s.airflow_direction === "tower" ? "タワー" : "";
          const lcd = s.lcd_display ? " · LCDあり" : "";
          const styleStr = style ? ` · ${style}` : "";
          return `空冷 高さ${s.height||"?"}mm${styleStr} · 最大${s.max_tdp||"?"}W${lcd}`;
        }
      }
      return "";
    }
    function formatDate(dt) {
      if (!dt) return "";
      return dt.slice(0, 10).replace(/-/g, "/");
    }

    // ── Toast ─────────────────────────────────────────────────────────────
    const toasts = ref([]);
    let toastId = 0;
    function toast(msg, type = "info") {
      const id = toastId++;
      toasts.value.push({ id, msg, type });
      setTimeout(() => { toasts.value = toasts.value.filter(t => t.id !== id); }, 3000);
    }

    // ── API Helpers ───────────────────────────────────────────────────────
    async function apiFetch(path, opts = {}) {
      const res = await fetch(API + path, {
        headers: { "Content-Type": "application/json", ...(opts.extraHeaders || {}) },
        ...opts,
      });
      if (res.status === 401) {
        // 認証エラー: パスワードをリセットして再認証を促す
        _adminPassword = "";
        throw new Error("管理者パスワードが間違っています");
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "エラーが発生しました" }));
        throw new Error(err.detail || "APIエラー");
      }
      return res.json();
    }
    async function adminFetch(path, opts = {}) {
      try {
        await requireAdmin();
      } catch (e) {
        throw new Error("認証がキャンセルされました");
      }
      return apiFetch(path, { ...opts, extraHeaders: { "X-Admin-Password": _adminPassword } });
    }

    // ── Load Home Stats ───────────────────────────────────────────────────
    async function loadStats() {
      try {
        const parts = await apiFetch("/api/parts");
        const builds = await apiFetch("/api/builds");
        const brands = await apiFetch("/api/parts/brands");
        stats.parts  = parts.length;
        stats.builds = builds.length;
        stats.brands = brands.length;
        recentBuilds.value = builds.slice(0, 3);
      } catch (e) { /* silent */ }
    }

    // ── Builder ───────────────────────────────────────────────────────────
    async function goBuilder() {
      if (!currentBuild.id) {
        await createNewBuild();
      }
      view.value = "builder";
      await loadCategoryParts(selectedCat.value);
    }

    async function newBuildAndGo() {
      await createNewBuild();
      view.value = "builder";
      await loadCategoryParts(selectedCat.value);
    }

    async function createNewBuild() {
      const res = await apiFetch("/api/builds", {
        method: "POST",
        body: JSON.stringify({ name: "新しい構成", purpose: "gaming", budget: 0 }),
      });
      currentBuild.id      = res.id;
      currentBuild.name    = "新しい構成";
      currentBuild.purpose = "gaming";
      // Clear selections
      for (const k of Object.keys(selectedParts)) delete selectedParts[k];
      for (const k of Object.keys(customPrices)) delete customPrices[k];
      compatIssues.value = [];
    }

    async function loadBuildAndGo(buildId) {
      try {
        const data = await apiFetch(`/api/builds/${buildId}`);
        currentBuild.id      = data.id;
        currentBuild.name    = data.name;
        currentBuild.purpose = data.purpose;
        buildNotes.value     = data.notes || "";
        // Restore selected parts
        for (const k of Object.keys(selectedParts)) delete selectedParts[k];
        for (const k of Object.keys(customPrices)) delete customPrices[k];
        for (const bp of (data.parts || [])) {
          bp.specs = typeof bp.specs === "string" ? JSON.parse(bp.specs) : (bp.specs || {});
          selectedParts[bp.category] = bp;
          if (bp.custom_price) {
            customPrices[bp.category] = { price: bp.custom_price, is_used: !!bp.is_used };
          }
        }
        view.value = "builder";
        await loadCategoryParts(selectedCat.value);
        await runCompatCheck();
      } catch (e) {
        toast("構成の読み込みに失敗しました", "error");
      }
    }

    async function saveBuildName() {
      if (!currentBuild.id) return;
      await apiFetch(`/api/builds/${currentBuild.id}`, {
        method: "PUT",
        body: JSON.stringify({ name: currentBuild.name, purpose: currentBuild.purpose }),
      });
    }

    // ── Build Notes ──────────────────────────────────────────────────────
    const buildNotes = ref("");
    let notesTimer = null;
    function debounceSaveNotes() {
      clearTimeout(notesTimer);
      notesTimer = setTimeout(async () => {
        if (!currentBuild.id) return;
        try {
          await apiFetch(`/api/builds/${currentBuild.id}`, {
            method: "PUT",
            body: JSON.stringify({ notes: buildNotes.value }),
          });
        } catch (e) { /* silent */ }
      }, 1000);
    }

    function getGpuSeries(name) {
      const n = name.toUpperCase();
      if (/RTX\s*50/.test(n))  return "RTX 50系";
      if (/RTX\s*40/.test(n))  return "RTX 40系";
      if (/RTX\s*30/.test(n))  return "RTX 30系";
      if (/RTX\s*20/.test(n))  return "RTX 20系";
      if (/GTX\s*16/.test(n))  return "GTX 16系";
      if (/GTX\s*10/.test(n))  return "GTX 10系";
      if (/RX\s*9/.test(n))    return "RX 9000系";
      if (/RX\s*7/.test(n))    return "RX 7000系";
      if (/RX\s*6/.test(n))    return "RX 6000系";
      if (/RX\s*5/.test(n))    return "RX 5000系";
      if (/RX\s*[45]8/.test(n)||/RX\s*57/.test(n)) return "RX 500系";
      if (/ARC/.test(n))       return "Intel Arc";
      return "";
    }

    async function selectCategory(cat) {
      selectedCat.value = cat;
      genFilter.value    = "";
      memCapFilter.value = "";
      memGenFilter.value = "";
      Object.keys(catFilters).forEach(k => { catFilters[k] = ""; });
      await loadCategoryParts(cat);
    }

    async function loadCategoryParts(cat) {
      loadingParts.value = true;
      try {
        const parts = await apiFetch(`/api/parts?category=${cat}`);
        parts.forEach(p => {
          if (typeof p.specs === "string") p.specs = JSON.parse(p.specs);
        });
        allParts.value = parts;
        filterParts();
        // バックグラウンドで上位パーツの価格を取得
        fetchVisiblePrices();
      } catch (e) {
        toast("パーツの読み込みに失敗しました", "error");
      } finally {
        loadingParts.value = false;
      }
    }

    function getCpuGeneration(name) {
      const n = name.toUpperCase();
      if (n.includes("ULTRA"))                         return "Intel Core Ultra (Arrow Lake)";
      if (/I[3579]-14\d{3}/.test(n))                  return "Intel 14世代";
      if (/I[3579]-13\d{3}/.test(n))                  return "Intel 13世代";
      if (/I[3579]-12\d{3}/.test(n))                  return "Intel 12世代";
      if (/I[3579]-11\d{3}/.test(n))                  return "Intel 11世代";
      if (/I[3579]-10\d{3}/.test(n))                  return "Intel 10世代";
      if (/I[3579]-[89]\d{3}/.test(n))                return "Intel 8-9世代";
      const amd = n.match(/RYZEN\s+\d+\s+(\d)\d{3}/);
      if (amd) {
        const g = {"9":"AMD Ryzen 9000系","8":"AMD Ryzen 8000系","7":"AMD Ryzen 7000系",
                   "5":"AMD Ryzen 5000系","3":"AMD Ryzen 3000系","2":"AMD Ryzen 2000系","1":"AMD Ryzen 1000系"};
        return g[amd[1]] || "";
      }
      return "";
    }

    function filterParts() {
      let parts = [...allParts.value];
      const q = searchQ.value.toLowerCase();
      if (q) {
        parts = parts.filter(p =>
          p.name.toLowerCase().includes(q) ||
          p.brand.toLowerCase().includes(q) ||
          p.model.toLowerCase().includes(q)
        );
      }
      // CPU 世代フィルター
      if (selectedCat.value === "cpu" && genFilter.value) {
        parts = parts.filter(p => getCpuGeneration(p.name + " " + p.model) === genFilter.value);
      }
      // メモリ 世代フィルター
      if (selectedCat.value === "memory" && memGenFilter.value) {
        parts = parts.filter(p => (p.specs?.memory_type || "") === memGenFilter.value);
      }
      // メモリ容量フィルター
      if (selectedCat.value === "memory" && memCapFilter.value) {
        const wantCap = parseInt(memCapFilter.value);
        parts = parts.filter(p => {
          const c    = p.specs?.capacity || 0;
          const mods = p.specs?.modules  || 1;
          const total = c * mods;
          if (memCapFilter.value === "128") return total >= 128;
          return total === wantCap;
        });
      }
      // GPU フィルター
      if (selectedCat.value === "gpu") {
        if (catFilters.gpu_series) parts = parts.filter(p => getGpuSeries(p.name) === catFilters.gpu_series);
        if (catFilters.gpu_vram)   parts = parts.filter(p => (p.specs?.vram || 0) === parseInt(catFilters.gpu_vram));
      }
      // マザーボード フィルター
      if (selectedCat.value === "motherboard") {
        if (catFilters.mb_socket)  parts = parts.filter(p => (p.specs?.socket || "").replace("Socket ", "").trim() === catFilters.mb_socket);
        if (catFilters.mb_form)    parts = parts.filter(p => (p.specs?.form_factor || "") === catFilters.mb_form);
        if (catFilters.mb_chipset) parts = parts.filter(p => (p.specs?.chipset || "").startsWith(catFilters.mb_chipset));
        if (catFilters.mb_wifi)    parts = parts.filter(p => catFilters.mb_wifi === "yes" ? !!p.specs?.wifi : !p.specs?.wifi);
        if (catFilters.mb_usbc)    parts = parts.filter(p => (p.specs?.usb_c_rear || 0) >= parseInt(catFilters.mb_usbc));
      }
      // ストレージ フィルター
      if (selectedCat.value === "storage") {
        if (catFilters.sto_type) parts = parts.filter(p => (p.specs?.type || "") === catFilters.sto_type);
        if (catFilters.sto_cap) {
          const cap = parseInt(catFilters.sto_cap);
          if (catFilters.sto_cap === "250")  parts = parts.filter(p => (p.specs?.capacity || 0) > 0 && (p.specs?.capacity || 0) <= 250);
          else if (catFilters.sto_cap === "4000") parts = parts.filter(p => (p.specs?.capacity || 0) >= 4000);
          else parts = parts.filter(p => { const c = p.specs?.capacity || 0; return c > cap * 0.6 && c <= cap * 1.4; });
        }
      }
      // 電源 フィルター
      if (selectedCat.value === "psu" && catFilters.psu_watt) {
        const w = parseInt(catFilters.psu_watt);
        if (catFilters.psu_watt === "450")  parts = parts.filter(p => (p.specs?.wattage || 0) > 0 && (p.specs?.wattage || 0) <= 500);
        else if (catFilters.psu_watt === "1000") parts = parts.filter(p => (p.specs?.wattage || 0) >= 1000);
        else parts = parts.filter(p => { const watt = p.specs?.wattage || 0; return watt > w - 75 && watt <= w + 75; });
      }
      // ケース フィルター
      if (selectedCat.value === "case" && catFilters.case_form) {
        parts = parts.filter(p => (p.specs?.form_factors || []).includes(catFilters.case_form));
      }
      // クーラー フィルター
      if (selectedCat.value === "cooler" && catFilters.cooler_type) {
        if (catFilters.cooler_type === "Air") {
          parts = parts.filter(p => p.specs?.type === "Air");
        } else if (catFilters.cooler_type.startsWith("AIO_")) {
          const size = parseInt(catFilters.cooler_type.split("_")[1]);
          parts = parts.filter(p => p.specs?.type === "AIO" && (p.specs?.aio_size || 0) === size);
        }
      }
      if (selectedCat.value === "cooler" && catFilters.cooler_airflow) {
        parts = parts.filter(p => (p.specs?.airflow_direction || "") === catFilters.cooler_airflow);
      }
      if (selectedCat.value === "cooler" && catFilters.cooler_lcd) {
        parts = parts.filter(p => p.specs?.lcd_display === true);
      }
      // カラーフィルター（全カテゴリ共通）
      if (catFilters.color) {
        parts = parts.filter(p => (p.specs?.colors || []).includes(catFilters.color));
      }
      // ソート
      if (sortBy.value === "score")      parts.sort((a, b) => (b.benchmark_score||0) - (a.benchmark_score||0));
      if (sortBy.value === "price_asc")  parts.sort((a, b) => a.reference_price - b.reference_price);
      if (sortBy.value === "price_desc") parts.sort((a, b) => b.reference_price - a.reference_price);
      if (sortBy.value === "name")       parts.sort((a, b) => a.name.localeCompare(b.name));
      if (sortBy.value === "mem_total")  parts.sort((a, b) => {
        const ta = (a.specs?.capacity||0)*(a.specs?.modules||1);
        const tb = (b.specs?.capacity||0)*(b.specs?.modules||1);
        return tb - ta;
      });
      if (sortBy.value === "mem_speed")   parts.sort((a, b) => (b.specs?.speed||0) - (a.specs?.speed||0));
      if (sortBy.value === "mem_single")  parts.sort((a, b) => (b.specs?.capacity||0) - (a.specs?.capacity||0));
      if (sortBy.value === "cooler_tdp")  parts.sort((a, b) => (b.specs?.max_tdp||0) - (a.specs?.max_tdp||0));
      if (sortBy.value === "cooler_aio")  parts.sort((a, b) => (b.specs?.aio_size||0) - (a.specs?.aio_size||0));
      if (sortBy.value === "cooler_height") parts.sort((a, b) => {
        // AIOは高さ0なので別扱い（AIOを後ろに）
        const ha = a.specs?.type === "AIO" ? 9999 : (a.specs?.height||0);
        const hb = b.specs?.type === "AIO" ? 9999 : (b.specs?.height||0);
        return ha - hb;
      });
      filteredParts.value = parts;
      // フィルター後の表示パーツの価格を取得
      fetchVisiblePrices();
    }

    async function selectPart(part) {
      if (!currentBuild.id) await createNewBuild();
      try {
        await apiFetch(`/api/builds/${currentBuild.id}/parts`, {
          method: "POST",
          body: JSON.stringify({ part_id: part.id, quantity: 1 }),
        });
        selectedParts[part.category] = part;
        // clear custom price when changing part
        delete customPrices[part.category];
        toast(`✅ ${part.brand} ${part.model} を追加しました`, "success");
        await runCompatCheck();
        // バックグラウンドで価格を自動取得・適用
        autoApplyPrice(part);
      } catch (e) {
        toast(e.message, "error");
      }
    }

    async function autoApplyPrice(part) {
      try {
        const res = await apiFetch(`/api/prices/${part.id}`);
        const cheapest = res.cheapest_new || res.cheapest_used;
        if (!cheapest) return;
        const isUsed = !res.cheapest_new && !!res.cheapest_used;
        const price = cheapest.price;
        // 既にユーザーが手動で変更していたら上書きしない
        if (customPrices[part.category]) return;
        // 選択済みのパーツが変わっていたら適用しない
        if (selectedParts[part.category]?.id !== part.id) return;
        customPrices[part.category] = { price, is_used: isUsed };
        if (currentBuild.id) {
          await apiFetch(`/api/builds/${currentBuild.id}/parts/${part.id}/price`, {
            method: "PUT",
            body: JSON.stringify({ custom_price: price, is_used: isUsed }),
          });
        }
        toast(`💴 ${part.brand} ${part.model}: ¥${price.toLocaleString()}${isUsed ? "（中古）" : ""}`, "success");
      } catch (e) { /* 自動取得失敗は無視 */ }
    }

    async function removePart(cat) {
      const part = selectedParts[cat];
      if (!part) return;
      // find build_part id via reload
      try {
        const data = await apiFetch(`/api/builds/${currentBuild.id}`);
        const bp = (data.parts || []).find(p => p.category === cat);
        if (bp) {
          // bp.id = parts table ID (after builds.py fix)
          await apiFetch(`/api/builds/${currentBuild.id}/parts/${bp.id}`, { method: "DELETE" });
        }
        delete selectedParts[cat];
        delete customPrices[cat];
        await runCompatCheck();
        toast("パーツを削除しました", "info");
      } catch (e) {
        toast("削除に失敗しました", "error");
      }
    }

    const currentCatLabel = computed(() => getCatLabel(selectedCat.value));

    // ── Compat ─────────────────────────────────────────────────────────────
    let compatTimer = null;
    async function runCompatCheck() {
      clearTimeout(compatTimer);
      compatTimer = setTimeout(async () => {
        const ids = Object.values(selectedParts).map(p => p.id).filter(Boolean);
        if (ids.length < 2) {
          compatIssues.value = [];
          return;
        }
        compatLoading.value = true;
        try {
          const res = await apiFetch("/api/compatibility/check?" + ids.map(id => `part_ids=${id}`).join("&"), { method: "POST" });
          compatIssues.value = [...(res.errors || []), ...(res.warnings || []), ...(res.ok || [])];
        } catch (e) {
          compatIssues.value = [];
        } finally {
          compatLoading.value = false;
        }
      }, 400);
    }

    // ── Price Modal ────────────────────────────────────────────────────────
    const SITE_LABELS = {
      kakaku: "価格.com", amazon: "Amazon", mercari: "メルカリ",
      yahoo_auction: "ヤフオク", yahoo_flea: "PayPayフリマ",
      janpara: "ジャンパラ", sofmap: "ソフマップ",
    };
    function siteLabel(key) { return SITE_LABELS[key] || key; }

    const priceModal = reactive({
      show: false, loading: false, tab: "new",
      partId: null, partName: "", currentPart: null,
      newPrices: [], usedPrices: [], cheapestNew: null, cheapestUsed: null,
      saleDetected: false, saleMessage: "", searchLinks: null,
      history: [], historyLoading: false,
    });

    async function loadPriceHistory(partId) {
      priceModal.historyLoading = true;
      priceModal.history = [];
      try {
        priceModal.history = await apiFetch(`/api/parts/${partId}/price-history`);
      } catch (e) { /* silent */ }
      finally { priceModal.historyLoading = false; }
    }

    async function showPriceModal(part) {
      priceModal.partId   = part.id;
      priceModal.partName = `${part.brand} ${part.model}`;
      priceModal.currentPart = part;
      priceModal.show     = true;
      priceModal.tab      = "new";
      await fetchPrice(part.id);
    }

    async function fetchPrice(partId, force = false) {
      priceModal.loading = true;
      priceModal.newPrices = [];
      priceModal.usedPrices = [];
      try {
        const res = await apiFetch(`/api/prices/${partId}${force ? "?force_refresh=true" : ""}`);
        priceModal.newPrices    = res.new_prices || [];
        priceModal.usedPrices   = res.used_prices || [];
        priceModal.saleDetected = res.sale_detected || false;
        priceModal.saleMessage  = res.sale_message || "";
        priceModal.searchLinks  = res.search_links || null;
        if (!res.scrape_success) {
          toast("自動取得できませんでした。下の検索リンクから手動で確認できます", "info");
        }
      } catch (e) {
        toast("価格取得に失敗しました。サイトへのアクセスを確認してください", "error");
      } finally {
        priceModal.loading = false;
      }
    }

    async function usePrice(price, isUsed) {
      const part = priceModal.currentPart;
      if (!part) return;
      customPrices[part.category] = { price, is_used: isUsed };
      // DBにも保存（リロード・出力時に反映させるため）
      if (currentBuild.id) {
        try {
          await apiFetch(`/api/builds/${currentBuild.id}/parts/${part.id}/price`, {
            method: "PUT",
            body: JSON.stringify({ custom_price: price, is_used: isUsed }),
          });
        } catch (e) { /* ローカル適用は完了しているので無視 */ }
      }
      toast(`¥${price.toLocaleString()} を適用しました`, "success");
      priceModal.show = false;
    }

    // ── Review Modal ───────────────────────────────────────────────────────
    const reviewModal = reactive({
      show: false,
      errorCount: 0,
      missingCats: [],
      fetchingCats: [],          // 価格取得中のカテゴリ (配列でVue追跡)
    });

    async function openReview() {
      const errors = compatIssues.value.filter(i => i.level === "error");
      reviewModal.errorCount = errors.length;
      reviewModal.missingCats = categories.filter(c => !selectedParts[c.key]);
      reviewModal.show = true;

      // 未取得パーツの価格を並列フェッチ
      const uncached = Object.entries(selectedParts).filter(([cat]) => !customPrices[cat]);
      if (uncached.length === 0) return;

      reviewModal.fetchingCats = uncached.map(([cat]) => cat);

      await Promise.allSettled(uncached.map(async ([cat, part]) => {
        try {
          const res = await apiFetch(`/api/prices/${part.id}`);
          const cheapest = res.cheapest_new || res.cheapest_used;
          if (cheapest && !customPrices[cat] && selectedParts[cat]?.id === part.id) {
            const isUsed = !res.cheapest_new && !!res.cheapest_used;
            customPrices[cat] = { price: cheapest.price, is_used: isUsed };
            if (currentBuild.id) {
              apiFetch(`/api/builds/${currentBuild.id}/parts/${part.id}/price`, {
                method: "PUT",
                body: JSON.stringify({ custom_price: cheapest.price, is_used: isUsed }),
              }).catch(() => {});
            }
          }
        } catch (e) { /* 取得失敗は無視 */ }
        finally {
          reviewModal.fetchingCats = reviewModal.fetchingCats.filter(c => c !== cat);
        }
      }));
    }

    // ── Sales Check ────────────────────────────────────────────────────────
    const salesModal = reactive({ show: false, loading: false, results: [] });

    async function checkFinalPrices() {
      if (!currentBuild.id) return;
      salesModal.show    = true;
      salesModal.loading = true;
      salesModal.results = [];
      try {
        const res = await apiFetch(`/api/prices/check-sales/${currentBuild.id}`);
        salesModal.results = res.sales || [];
      } catch (e) {
        toast("セール確認に失敗しました", "error");
      } finally {
        salesModal.loading = false;
      }
    }

    // ── Export ─────────────────────────────────────────────────────────────
    function exportExcel() { exportExcelById(currentBuild.id); }
    function exportPdf()   { exportPdfById(currentBuild.id); }
    function exportExcelById(id) { if (id) window.open(`/api/export/excel/${id}`); }
    function exportPdfById(id)   { if (id) window.open(`/api/export/pdf/${id}`); }

    // ── Suggest ────────────────────────────────────────────────────────────
    const suggestForm    = reactive({ budget: 100000, purpose: "gaming" });
    const suggestResults = ref([]);
    const suggestLoading = ref(false);
    const selectedSuggest = ref(null);

    const purposes = [
      { val: "gaming",      icon: "🎮", label: "ゲーミング" },
      { val: "workstation", icon: "💼", label: "ワークステーション" },
      { val: "office",      icon: "📁", label: "オフィス" },
      { val: "streaming",   icon: "🎥", label: "配信・実況" },
      { val: "balanced",    icon: "⚖️", label: "バランス型" },
      { val: "budget",      icon: "💰", label: "コスパ重視" },
    ];

    async function runSuggest() {
      suggestLoading.value = true;
      suggestResults.value = [];
      selectedSuggest.value = null;
      try {
        const res = await apiFetch("/api/suggest", {
          method: "POST",
          body: JSON.stringify({ budget: suggestForm.budget, purpose: suggestForm.purpose }),
        });
        // parse specs
        for (const plan of res.suggestions || []) {
          for (const [cat, part] of Object.entries(plan.parts || {})) {
            if (typeof part.specs === "string") part.specs = JSON.parse(part.specs);
          }
        }
        suggestResults.value = res.suggestions || [];
      } catch (e) {
        toast("サジェストに失敗しました", "error");
      } finally {
        suggestLoading.value = false;
      }
    }

    async function loadSuggestIntoBuild(plan) {
      await createNewBuild();
      for (const [cat, part] of Object.entries(plan.parts || {})) {
        try {
          await apiFetch(`/api/builds/${currentBuild.id}/parts`, {
            method: "POST",
            body: JSON.stringify({ part_id: part.id, quantity: 1 }),
          });
          selectedParts[cat] = part;
        } catch (e) { /* skip */ }
      }
      view.value = "builder";
      await loadCategoryParts(selectedCat.value);
      await runCompatCheck();
      toast("サジェスト構成を読み込みました！", "success");
    }

    const compatModal = reactive({ show: false, issues: [] });
    function showSuggestCompat(plan) {
      compatModal.issues = plan.compatibility || [];
      compatModal.show   = true;
    }

    // ── Saved Builds ───────────────────────────────────────────────────────
    const savedBuilds = ref([]);
    async function loadBuilds() {
      try {
        savedBuilds.value = await apiFetch("/api/builds");
      } catch (e) { toast("構成一覧の取得に失敗しました", "error"); }
    }
    async function deleteBuild(id) {
      if (!confirm("この構成を削除しますか？")) return;
      await apiFetch(`/api/builds/${id}`, { method: "DELETE" });
      await loadBuilds();
      toast("構成を削除しました", "info");
    }

    // ── Parts DB ───────────────────────────────────────────────────────────
    const dbParts  = ref([]);
    const dbFilter = reactive({ category: "", q: "" });
    const dbSort   = reactive({ col: "name", asc: true });
    const dbSortedParts = computed(() => {
      const list = [...dbParts.value];
      const { col, asc } = dbSort;
      list.sort((a, b) => {
        const va = a[col] ?? 0;
        const vb = b[col] ?? 0;
        if (typeof va === "string") return asc ? va.localeCompare(vb, "ja") : vb.localeCompare(va, "ja");
        return asc ? va - vb : vb - va;
      });
      return list;
    });
    function sortDbBy(col) {
      if (dbSort.col === col) { dbSort.asc = !dbSort.asc; }
      else { dbSort.col = col; dbSort.asc = (col === "name" || col === "brand"); }
    }
    async function loadPartsDb() {
      try {
        const params = new URLSearchParams();
        if (dbFilter.category) params.set("category", dbFilter.category);
        if (dbFilter.q)        params.set("q", dbFilter.q);
        const parts = await apiFetch(`/api/parts?${params}`);
        parts.forEach(p => {
          if (typeof p.specs === "string") p.specs = JSON.parse(p.specs);
        });
        dbParts.value = parts;
      } catch (e) { toast("パーツDBの取得に失敗しました", "error"); }
    }

    const partFormModal = reactive({
      show: false, isEdit: false,
      data: {},
      specsJson: "{}",
      editId: null,
    });
    function openAddPartModal() {
      partFormModal.isEdit = false;
      partFormModal.editId = null;
      partFormModal.data = { category: "cpu", brand: "", name: "", model: "", tdp: 0, benchmark_score: 0, reference_price: 0, release_year: new Date().getFullYear(), notes: "" };
      partFormModal.specsJson = "{}";
      partFormModal.show = true;
    }
    function openEditPartModal(part) {
      partFormModal.isEdit = true;
      partFormModal.editId = part.id;
      partFormModal.data = { ...part };
      partFormModal.specsJson = JSON.stringify(part.specs || {}, null, 2);
      partFormModal.show = true;
    }
    async function savePart() {
      let specs = {};
      try { specs = JSON.parse(partFormModal.specsJson); } catch (e) {
        toast("スペックのJSON形式が不正です", "error"); return;
      }
      const payload = { ...partFormModal.data, specs };
      try {
        if (partFormModal.isEdit) {
          await adminFetch(`/api/parts/${partFormModal.editId}`, { method: "PUT", body: JSON.stringify(payload) });
          toast("パーツを更新しました", "success");
        } else {
          await adminFetch("/api/parts", { method: "POST", body: JSON.stringify(payload) });
          toast("パーツを追加しました", "success");
        }
        partFormModal.show = false;
        await loadPartsDb();
        await loadStats();
      } catch (e) {
        toast(e.message, "error");
      }
    }
    async function deletePart(id) {
      if (!confirm("このパーツを削除しますか？")) return;
      try {
        await adminFetch(`/api/parts/${id}`, { method: "DELETE" });
        await loadPartsDb();
        await loadStats();
        toast("パーツを削除しました", "info");
      } catch (e) {
        toast(e.message, "error");
      }
    }

    // ── Sync ──────────────────────────────────────────────────────────────
    const syncCats = categories;
    const syncModal = reactive({
      show: false, running: false, started: false,
      selected: ["cpu", "gpu", "motherboard", "memory", "storage", "psu", "case", "cooler"],
      maxPages: 10,
      progress: {},
    });
    const syncHistory = ref([]);

    async function loadSyncHistory() {
      try { syncHistory.value = await apiFetch("/api/sync/history"); } catch (e) { /* silent */ }
    }

    async function openSyncModalWithAuth() {
      try {
        await requireAdmin();
      } catch (e) { return; }
      syncModal.show = true;
      syncModal.started = false;
      syncModal.running = false;
      syncModal.progress = {};
      await loadSyncHistory();
    }

    // 後方互換: HTMLから直接呼べるようにも残す
    function openSyncModal() { openSyncModalWithAuth(); }

    let syncPollTimer = null;
    async function startSync() {
      syncModal.started = true;
      syncModal.running = true;
      syncModal.progress = Object.fromEntries(syncModal.selected.map(c => [c, "待機中"]));
      try {
        await apiFetch(`/api/sync/start`, {
          method: "POST",
          body: JSON.stringify({ categories: syncModal.selected, max_pages: syncModal.maxPages }),
          extraHeaders: { "X-Admin-Password": _adminPassword },
        });
        syncPollTimer = setInterval(async () => {
          try {
            const status = await apiFetch("/api/sync/status");
            syncModal.progress = status.progress || {};
            if (!status.running) {
              syncModal.running = false;
              clearInterval(syncPollTimer);
              await loadStats();
              await loadSyncHistory();
              toast(`同期完了！`, "success");
            }
          } catch (e) { /* ignore */ }
        }, 2000);
      } catch (e) {
        syncModal.running = false;
        toast(e.message || "同期の開始に失敗しました", "error");
      }
    }

    // ── Compare ────────────────────────────────────────────────────────────
    const compareList = ref([]);
    const showCompareModal = ref(false);
    function toggleCompare(part) {
      const idx = compareList.value.findIndex(p => p.id === part.id);
      if (idx >= 0) {
        compareList.value.splice(idx, 1);
      } else {
        if (compareList.value.length >= 4) {
          toast("比較は最大4件です", "info"); return;
        }
        compareList.value.push(part);
      }
    }

    // ── Share URL ─────────────────────────────────────────────────────────
    const shareView = reactive({ show: false, loading: false, build: null });

    async function copyShareUrl() {
      if (!currentBuild.id) return;
      await copyShareUrlById(currentBuild.id);
    }
    async function copyShareUrlById(buildId) {
      try {
        const res = await apiFetch(`/api/builds/${buildId}/share-url`);
        const url = `${location.origin}/#share/${res.share_token}`;
        await navigator.clipboard.writeText(url);
        toast("共有URLをコピーしました！", "success");
      } catch (e) {
        toast("URLのコピーに失敗しました", "error");
      }
    }
    async function loadShareBuild(token) {
      shareView.show = true;
      shareView.loading = true;
      shareView.build = null;
      try {
        shareView.build = await apiFetch(`/api/builds/share/${token}`);
        // OGPを動的に更新
        document.title = `${shareView.build.name} — PC Builder`;
        document.querySelector('meta[property="og:title"]')?.setAttribute("content", shareView.build.name);
      } catch (e) {
        toast("共有構成が見つかりません", "error");
        shareView.show = false;
      } finally {
        shareView.loading = false;
      }
    }
    async function copySharedBuild(build) {
      try {
        const res = await apiFetch("/api/builds", {
          method: "POST",
          body: JSON.stringify({ name: build.name + " (コピー)", purpose: build.purpose || "balanced" }),
        });
        const newId = res.id;
        for (const p of (build.parts || [])) {
          await apiFetch(`/api/builds/${newId}/parts`, {
            method: "POST",
            body: JSON.stringify({ part_id: p.id, quantity: p.quantity || 1, custom_price: p.custom_price }),
          }).catch(() => {});
        }
        shareView.show = false;
        toast("構成をコピーしました！ビルダーで確認できます", "success");
        await loadBuildAndGo(newId);
      } catch (e) {
        toast("コピーに失敗しました", "error");
      }
    }

    // ── Recalc Benchmarks ─────────────────────────────────────────────────
    const recalcLoading = ref(false);
    async function recalcBenchmarks() {
      recalcLoading.value = true;
      try {
        const res = await adminFetch("/api/sync/recalc-benchmarks", { method: "POST" });
        toast(`スコア再計算完了: ${res.updated}件更新`, "success");
        await loadCategoryParts(selectedCat.value);
      } catch (e) {
        toast(e.message || "再計算に失敗しました", "error");
      } finally {
        recalcLoading.value = false;
      }
    }

    // ── Init ───────────────────────────────────────────────────────────────
    onMounted(async () => {
      await loadStats();
      // URLハッシュで共有ビルドを開く
      const hash = location.hash;
      if (hash.startsWith("#share/")) {
        const token = hash.replace("#share/", "");
        if (token) await loadShareBuild(token);
      }
    });

    return {
      // core
      view, stats, recentBuilds, features, categories,
      mobileMenuOpen,
      // admin auth
      adminModal, confirmAdminPassword,
      // builder
      currentBuild, selectedCat, selectedParts, customPrices,
      allParts, filteredParts, loadingParts, searchQ, sortBy, maxScore,
      genFilter, memCapFilter, memGenFilter, getCpuGeneration, catFilters, getGpuSeries,
      partPriceCache, getDisplayPrice, isPriceLoading, isPriceUsed, fetchVisiblePrices,
      recalcLoading, recalcBenchmarks,
      compatIssues, compatLoading, totalTdp, psuWattage, powerPercent, powerColor,
      totalPrice, currentCatLabel,
      goBuilder, newBuildAndGo, loadBuildAndGo, saveBuildName,
      selectCategory, selectPart, removePart, filterParts,
      getCatIcon, getCatLabel, getSelectedPart, catHasError, getEffectivePrice, getPartSubtext, formatDate,
      // build notes
      buildNotes, debounceSaveNotes,
      // review
      reviewModal, openReview,
      // price modal + history
      priceModal, showPriceModal, fetchPrice, usePrice, siteLabel, loadPriceHistory,
      // sales
      salesModal, checkFinalPrices,
      // export
      exportExcel, exportPdf, exportExcelById, exportPdfById,
      // suggest
      suggestForm, suggestResults, suggestLoading, selectedSuggest, purposes,
      runSuggest, loadSuggestIntoBuild,
      compatModal, showSuggestCompat,
      // builds list
      savedBuilds, loadBuilds, deleteBuild,
      // parts db
      dbParts, dbFilter, loadPartsDb, dbSort, dbSortedParts, sortDbBy,
      partFormModal, openAddPartModal, openEditPartModal, savePart, deletePart,
      toasts,
      // sync
      syncModal, syncCats, openSyncModal, openSyncModalWithAuth, startSync,
      syncHistory, loadSyncHistory,
      // compare
      compareList, showCompareModal, toggleCompare,
      // share
      shareView, copyShareUrl, copyShareUrlById, loadShareBuild, copySharedBuild,
    };
  },
}).mount("#root");
