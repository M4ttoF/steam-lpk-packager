const { createApp, ref, onMounted, nextTick } = Vue;

createApp({
    setup() {
        const urls = ref('');
        const isProcessing = ref(false);
        const log = ref([]);
        const packages = ref([]);
        const terminal = ref(null);

        const appendLog = (text, type = 'info') => {
            log.value.push({ text, type });
            nextTick(() => {
                if (terminal.value) {
                    terminal.value.scrollTop = terminal.value.scrollHeight;
                }
            });
        };

        const clearLog = () => {
            log.value = [];
        };

        // API Call: Fetch pre-existing ZIPs
        const fetchPackages = async () => {
            try {
                const res = await fetch('/api/packages');
                packages.value = await res.json();
            } catch (err) {
                console.error("Failed to load packages:", err);
            }
        };

        // Action: Run Report (Dry-run wrapper)
        const runReport = async () => {
            if (!urls.value.trim()) return;
            isProcessing.value = true;
            clearLog();
            appendLog("📡 Fetching Dry Run Report from Steam Web API...", "info");

            try {
                const response = await fetch('/api/dry-run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ urls: urls.value })
                });
                
                const data = await response.json();
                if (data.error) {
                    appendLog(`❌ Error: ${data.error}`, "error");
                } else {
                    // Split the terminal stdout rollups into neat log lines
                    const lines = data.output.split('\n');
                    lines.forEach(line => {
                        if (line.trim()) {
                            if (line.includes('❌') || line.includes('[CRITICAL WARNING]')) {
                                appendLog(line, 'error');
                            } else if (line.includes('⚠️') || line.includes('[WARNING]')) {
                                appendLog(line, 'warning');
                            } else if (line.includes('✅') || line.includes('🎉')) {
                                appendLog(line, 'success');
                            } else {
                                appendLog(line, 'info');
                            }
                        }
                    });
                }
            } catch (err) {
                appendLog(`❌ Network error while requesting report: ${err.message}`, "error");
            } finally {
                isProcessing.value = false;
            }
        };

        // Action: Download & Package Batch (using SSE streaming)
        const startPackaging = () => {
            if (!urls.value.trim()) return;
            isProcessing.value = true;
            clearLog();
            appendLog("🚀 Starting Batch Packaging Job...", "info");

            // Setup Server-Sent Events stream
            const eventSource = new EventSource(`/api/process-stream?urls=${encodeURIComponent(urls.value)}`);

            eventSource.addEventListener('stdout', (e) => {
                const text = JSON.parse(e.data);
                // Handle newlines
                const lines = text.split('\n');
                lines.forEach(line => {
                    if (line.trim()) {
                        if (line.includes('✅') || line.includes('🎉') || line.includes('Outcome:')) {
                            appendLog(line, 'success');
                        } else if (line.includes('⚠️') || line.includes('[WARNING]')) {
                            appendLog(line, 'warning');
                        } else if (line.includes('❌') || line.includes('[ERROR]')) {
                            appendLog(line, 'error');
                        } else {
                            appendLog(line, 'info');
                        }
                    }
                });
            });

            eventSource.addEventListener('stderr', (e) => {
                const text = JSON.parse(e.data);
                appendLog(text, 'error');
            });

            eventSource.addEventListener('exit', (e) => {
                const { code } = JSON.parse(e.data);
                if (code === 0) {
                    appendLog("✨ Batch extraction and packaging completed successfully!", "success");
                } else {
                    appendLog(`⚠️ Process terminated with code: ${code}`, "warning");
                }
                eventSource.close();
                isProcessing.value = false;
                fetchPackages(); // Reload packages list to catch the new ones
            });

            eventSource.onerror = (err) => {
                appendLog("❌ Connection to batch execution server lost.", "error");
                eventSource.close();
                isProcessing.value = false;
            };
        };

        onMounted(() => {
            fetchPackages();
        });

        return {
            urls,
            isProcessing,
            log,
            packages,
            terminal,
            runReport,
            startPackaging,
            clearLog,
            fetchPackages
        };
    }
}).mount('#app');
