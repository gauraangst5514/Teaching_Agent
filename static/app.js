/**
 * TeachAI — Frontend Application
 * Vanilla JavaScript · No frameworks
 */

(function () {
    "use strict";

    /* ───────────────────────────────────────────
       1. DOM Ready
    ─────────────────────────────────────────── */
    document.addEventListener("DOMContentLoaded", () => {
        initSidebar();
        initDropzone();
        initAutoTextarea();
        initQuickQuestion();
        initScoreGauge();
        initDashboardFilters();
        initDashboardSort();
        initFormSubmission();
        initSubmissionTypeToggle();
        initIntersectionAnimations();
        initContextualChat();
        initFeedbackTabs();
        initMarkdownParsing();
    });

    /* ───────────────────────────────────────────
       2. Sidebar Toggle (Mobile)
    ─────────────────────────────────────────── */
    function initSidebar() {
        const toggle = document.getElementById("sidebarToggle");
        const sidebar = document.getElementById("sidebar");
        const overlay = document.getElementById("sidebarOverlay");

        if (!toggle || !sidebar) return;

        function openSidebar() {
            sidebar.classList.add("sidebar--open");
            if (overlay) overlay.classList.add("sidebar-overlay--visible");
            document.body.style.overflow = "hidden";
        }

        function closeSidebar() {
            sidebar.classList.remove("sidebar--open");
            if (overlay) overlay.classList.remove("sidebar-overlay--visible");
            document.body.style.overflow = "";
        }

        toggle.addEventListener("click", () => {
            sidebar.classList.contains("sidebar--open") ? closeSidebar() : openSidebar();
        });

        if (overlay) overlay.addEventListener("click", closeSidebar);
    }

    /* ───────────────────────────────────────────
       3. Drag-and-Drop Upload
    ─────────────────────────────────────────── */
    function initDropzone() {
        const dropZone = document.getElementById("dropZone");
        const fileInput = document.getElementById("fileInput");
        const dropContent = document.getElementById("dropzoneContent");
        const previewArea = document.getElementById("dropzonePreview");
        const previewImage = document.getElementById("previewImage");
        const previewFileName = document.getElementById("previewFileName");
        const previewFileSize = document.getElementById("previewFileSize");
        const removeBtn = document.getElementById("removeFile");

        if (!dropZone || !fileInput) return;

        // Click to open file dialog
        dropZone.addEventListener("click", (e) => {
            if (e.target === removeBtn || e.target.closest("#removeFile")) return;
            fileInput.click();
        });

        // Keyboard accessibility
        dropZone.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                fileInput.click();
            }
        });

        // Drag events
        ["dragenter", "dragover"].forEach((evt) => {
            dropZone.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add("dropzone--active");
            });
        });

        ["dragleave", "drop"].forEach((evt) => {
            dropZone.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove("dropzone--active");
            });
        });

        dropZone.addEventListener("drop", (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                fileInput.files = files;
                showPreview(files[0]);
            }
        });

        fileInput.addEventListener("change", () => {
            if (fileInput.files.length > 0) {
                showPreview(fileInput.files[0]);
            }
        });

        // Remove file
        if (removeBtn) {
            removeBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                fileInput.value = "";
                hidePreview();
            });
        }

        function showPreview(file) {
            if (!previewArea || !dropContent) return;

            if (previewFileName) previewFileName.textContent = file.name;
            if (previewFileSize) previewFileSize.textContent = formatFileSize(file.size);

            if (file.type.startsWith("image/") && previewImage) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    previewImage.src = e.target.result;
                    previewImage.style.display = "block";
                };
                reader.readAsDataURL(file);
            } else if (previewImage) {
                previewImage.style.display = "none";
            }

            dropContent.style.display = "none";
            previewArea.style.display = "flex";
            dropZone.classList.add("dropzone--has-file");
        }

        function hidePreview() {
            if (dropContent) dropContent.style.display = "flex";
            if (previewArea) previewArea.style.display = "none";
            if (previewImage) {
                previewImage.src = "";
                previewImage.style.display = "none";
            }
            dropZone.classList.remove("dropzone--has-file");
        }
    }

    /* ───────────────────────────────────────────
       4. Auto-resize Textarea
    ─────────────────────────────────────────── */
    function initAutoTextarea() {
        document.querySelectorAll(".form-textarea--auto").forEach((ta) => {
            function resize() {
                ta.style.height = "auto";
                ta.style.height = ta.scrollHeight + "px";
            }
            ta.addEventListener("input", resize);
            resize();
        });
    }

    /* ───────────────────────────────────────────
       5. Quick Question AJAX
    ─────────────────────────────────────────── */
    function initQuickQuestion() {
        const askBtn = document.getElementById("askAiBtn");
        const input = document.getElementById("quickQuestionInput");
        const responseArea = document.getElementById("aiResponseArea");
        const responseContent = document.getElementById("aiResponseContent");
        const askLoader = document.getElementById("askLoader");

        if (!askBtn || !input) return;

        askBtn.addEventListener("click", async () => {
            const question = input.value.trim();
            if (!question) {
                input.focus();
                input.classList.add("form-input--error");
                setTimeout(() => input.classList.remove("form-input--error"), 1500);
                return;
            }

            // Show loading
            const btnText = askBtn.querySelector(".btn__text");
            if (btnText) btnText.style.display = "none";
            if (askLoader) askLoader.style.display = "inline-flex";
            askBtn.disabled = true;

            try {
                const res = await fetch("/ask", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ question: question }),
                });
                const data = await res.json();

                if (responseArea) responseArea.style.display = "block";
                if (responseContent) {
                    responseContent.textContent = "";
                    typeWriter(responseContent, data.answer || "No response received.");
                }
            } catch (err) {
                if (responseArea) responseArea.style.display = "block";
                if (responseContent) {
                    responseContent.textContent =
                        "Sorry, something went wrong. Please try again.";
                }
            } finally {
                if (btnText) btnText.style.display = "inline";
                if (askLoader) askLoader.style.display = "none";
                askBtn.disabled = false;
            }
        });

        // Enter to send (Shift+Enter for newline)
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                askBtn.click();
            }
        });
    }

    /** Typing animation for AI responses */
    function typeWriter(el, text, speed) {
        speed = speed || 12;
        let i = 0;
        el.textContent = "";
        el.classList.add("ai-response__content--typing");

        function tick() {
            if (i < text.length) {
                el.textContent += text.charAt(i);
                i++;
                setTimeout(tick, speed);
            } else {
                el.classList.remove("ai-response__content--typing");
            }
        }
        tick();
    }

    /* ───────────────────────────────────────────
       6. Animated Score Gauge
    ─────────────────────────────────────────── */
    function initScoreGauge() {
        const gauge = document.getElementById("scoreGauge");
        if (!gauge) return;

        const score = parseInt(gauge.dataset.score, 10) || 0;
        const circle = document.getElementById("scoreCircle");
        const valueEl = document.getElementById("scoreValue");

        // Determine color based on score
        let color;
        if (score >= 70) color = "var(--accent-success)";
        else if (score >= 40) color = "var(--accent-warning)";
        else color = "var(--accent-danger)";

        // Animate from 0 to score
        let current = 0;
        const duration = 1200;
        const stepTime = 16;
        const steps = duration / stepTime;
        const increment = score / steps;

        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        animateGauge();
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.3 }
        );
        observer.observe(gauge);

        function animateGauge() {
            const timer = setInterval(() => {
                current += increment;
                if (current >= score) {
                    current = score;
                    clearInterval(timer);
                }

                const pct = Math.round(current);
                if (valueEl) valueEl.textContent = pct;

                if (circle) {
                    const deg = (current / 100) * 360;
                    circle.style.background = `conic-gradient(${color} ${deg}deg, rgba(255,255,255,0.05) ${deg}deg)`;
                }
            }, stepTime);
        }
    }

    /* ───────────────────────────────────────────
       7. Dashboard Search & Filters
    ─────────────────────────────────────────── */
    function initDashboardFilters() {
        const searchInput = document.getElementById("searchInput");
        const statusFilter = document.getElementById("statusFilter");
        const typeFilter = document.getElementById("typeFilter");
        const tableBody = document.getElementById("tableBody");

        if (!tableBody) return;

        function applyFilters() {
            const query = searchInput ? searchInput.value.toLowerCase() : "";
            const status = statusFilter ? statusFilter.value : "";
            const type = typeFilter ? typeFilter.value : "";

            const rows = tableBody.querySelectorAll(".data-table__row");
            let visibleCount = 0;

            rows.forEach((row) => {
                const studentName = row.dataset.student || "";
                const rowType = row.dataset.type || "";
                const rowStatus = row.dataset.status || "";
                const rowText = row.textContent.toLowerCase();

                const matchesSearch = !query || rowText.includes(query);
                const matchesStatus = !status || rowStatus === status;
                const matchesType = !type || rowType === type;

                if (matchesSearch && matchesStatus && matchesType) {
                    row.style.display = "";
                    visibleCount++;
                } else {
                    row.style.display = "none";
                }
            });
        }

        if (searchInput) searchInput.addEventListener("input", applyFilters);
        if (statusFilter) statusFilter.addEventListener("change", applyFilters);
        if (typeFilter) typeFilter.addEventListener("change", applyFilters);
    }

    /* ───────────────────────────────────────────
       8. Dashboard Table Sorting
    ─────────────────────────────────────────── */
    function initDashboardSort() {
        const table = document.getElementById("submissionsTable");
        if (!table) return;

        const headers = table.querySelectorAll(".data-table__th--sortable");
        let currentSort = { key: null, dir: "asc" };

        headers.forEach((th) => {
            th.addEventListener("click", () => {
                const key = th.dataset.sort;
                if (currentSort.key === key) {
                    currentSort.dir = currentSort.dir === "asc" ? "desc" : "asc";
                } else {
                    currentSort.key = key;
                    currentSort.dir = "asc";
                }

                // Update header visuals
                headers.forEach((h) => h.classList.remove("data-table__th--asc", "data-table__th--desc"));
                th.classList.add(`data-table__th--${currentSort.dir}`);

                sortTable(key, currentSort.dir);
            });
        });

        function sortTable(key, dir) {
            const tbody = document.getElementById("tableBody");
            if (!tbody) return;

            const rows = Array.from(tbody.querySelectorAll(".data-table__row"));

            rows.sort((a, b) => {
                let valA, valB;

                switch (key) {
                    case "id":
                        valA = parseInt(a.querySelector(".table-id").textContent.replace("#", ""), 10);
                        valB = parseInt(b.querySelector(".table-id").textContent.replace("#", ""), 10);
                        break;
                    case "student":
                        valA = (a.dataset.student || "").toLowerCase();
                        valB = (b.dataset.student || "").toLowerCase();
                        return dir === "asc" ? valA.localeCompare(valB) : valB.localeCompare(valA);
                    case "type":
                        valA = (a.dataset.type || "").toLowerCase();
                        valB = (b.dataset.type || "").toLowerCase();
                        return dir === "asc" ? valA.localeCompare(valB) : valB.localeCompare(valA);
                    case "score":
                        valA = parseFloat(a.dataset.score) || 0;
                        valB = parseFloat(b.dataset.score) || 0;
                        break;
                    case "status":
                        valA = (a.dataset.status || "").toLowerCase();
                        valB = (b.dataset.status || "").toLowerCase();
                        return dir === "asc" ? valA.localeCompare(valB) : valB.localeCompare(valA);
                    case "date":
                        valA = a.dataset.date || "";
                        valB = b.dataset.date || "";
                        return dir === "asc" ? valA.localeCompare(valB) : valB.localeCompare(valA);
                    default:
                        return 0;
                }

                return dir === "asc" ? valA - valB : valB - valA;
            });

            rows.forEach((row) => tbody.appendChild(row));
        }
    }

    /* ───────────────────────────────────────────
       9. Form Submission Loading State
    ─────────────────────────────────────────── */
    function initFormSubmission() {
        const form = document.getElementById("uploadForm");
        const submitBtn = document.getElementById("submitBtn");
        const submitLoader = document.getElementById("submitLoader");

        if (!form || !submitBtn) return;

        form.addEventListener("submit", () => {
            const btnText = submitBtn.querySelector(".btn__text");
            if (btnText) btnText.style.display = "none";
            if (submitLoader) submitLoader.style.display = "inline-flex";
            submitBtn.disabled = true;
            submitBtn.classList.add("btn--loading");
        });
    }

    /* ───────────────────────────────────────────
       10. Submission Type Toggle
    ─────────────────────────────────────────── */
    function initSubmissionTypeToggle() {
        const typeSelect = document.getElementById("submissionType");
        const questionGroup = document.getElementById("questionTextGroup");

        if (!typeSelect || !questionGroup) return;

        typeSelect.addEventListener("change", () => {
            if (typeSelect.value === "question") {
                questionGroup.style.display = "block";
                questionGroup.style.animation = "fade-in 0.3s ease";
            } else {
                questionGroup.style.display = "none";
            }
        });
    }

    /* ───────────────────────────────────────────
       11. Intersection Observer Animations
    ─────────────────────────────────────────── */
    function initIntersectionAnimations() {
        const animTargets = document.querySelectorAll(
            ".card, .stat-card, .submission-card, .feedback-section, .overall-feedback"
        );

        if (!animTargets.length) return;

        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("animate-in");
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0, rootMargin: "50px" }
        );

        animTargets.forEach((el) => observer.observe(el));
    }

    /* ───────────────────────────────────────────
       Utility: Format file size
    ─────────────────────────────────────────── */
    function formatFileSize(bytes) {
        if (bytes === 0) return "0 Bytes";
        const k = 1024;
        const sizes = ["Bytes", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
    }

    /* ───────────────────────────────────────────
       12. Contextual Submission Chat
    ─────────────────────────────────────────── */
    function initContextualChat() {
        const chatContainer = document.getElementById("submissionChat");
        if (!chatContainer) return;

        const subId = chatContainer.dataset.id;
        const historyEl = document.getElementById("chatHistory");
        const inputEl = document.getElementById("chatInput");
        const sendBtn = document.getElementById("chatSendBtn");
        const loaderEl = document.getElementById("chatLoader");

        // Load History
        async function loadHistory() {
            try {
                const res = await fetch(`/api/submission/${subId}/chat`);
                if (!res.ok) return;
                const data = await res.json();
                
                historyEl.innerHTML = "";
                if (data.history && data.history.length > 0) {
                    data.history.forEach(msg => appendMessage(msg.role, msg.content));
                } else {
                    historyEl.innerHTML = '<div class="chat-msg chat-msg--system">Ask any question about your submission!</div>';
                }
                scrollToBottom();
            } catch (e) {
                console.error("Failed to load chat history", e);
            }
        }

        function appendMessage(role, text) {
            // Remove system placeholder if it exists
            const placeholder = historyEl.querySelector('.chat-msg--system');
            if (placeholder) placeholder.remove();

            const msgDiv = document.createElement("div");
            msgDiv.className = `chat-msg chat-msg--${role}`;
            
            const contentDiv = document.createElement("div");
            contentDiv.className = "chat-msg__bubble markdown-prose";
            
            if (role === "assistant" && typeof marked !== "undefined") {
                contentDiv.innerHTML = marked.parse(text);
            } else {
                contentDiv.textContent = text;
            }
            
            msgDiv.appendChild(contentDiv);
            historyEl.appendChild(msgDiv);
            scrollToBottom();
        }

        function scrollToBottom() {
            historyEl.scrollTop = historyEl.scrollHeight;
        }

        async function sendMessage() {
            const text = inputEl.value.trim();
            if (!text) return;

            // Optimistic UI update
            appendMessage("user", text);
            inputEl.value = "";
            inputEl.style.height = "auto";
            
            // Loading state
            sendBtn.disabled = true;
            sendBtn.querySelector(".btn__text").style.display = "none";
            loaderEl.style.display = "inline-flex";

            // Temporary pending bubble
            const pendingDiv = document.createElement("div");
            pendingDiv.className = "chat-msg chat-msg--assistant chat-msg--pending";
            pendingDiv.innerHTML = '<div class="chat-msg__bubble">...</div>';
            historyEl.appendChild(pendingDiv);
            scrollToBottom();

            try {
                const res = await fetch(`/api/submission/${subId}/chat`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ question: text }),
                });
                const data = await res.json();
                
                pendingDiv.remove();
                
                if (data.error) {
                    appendMessage("system", data.error);
                } else {
                    appendMessage("assistant", data.answer);
                }
            } catch (err) {
                pendingDiv.remove();
                appendMessage("system", "Failed to connect. Please try again.");
            } finally {
                sendBtn.disabled = false;
                sendBtn.querySelector(".btn__text").style.display = "inline";
                loaderEl.style.display = "none";
            }
        }

        sendBtn.addEventListener("click", sendMessage);
        inputEl.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Initialize
        loadHistory();
    }
    /* ───────────────────────────────────────────
       13. Feedback Tabs
    ─────────────────────────────────────────── */
    function initFeedbackTabs() {
        const tabs = document.querySelectorAll(".feedback-tab");
        const contents = document.querySelectorAll(".feedback-tab-content");

        if (!tabs.length) return;

        tabs.forEach(tab => {
            tab.addEventListener("click", () => {
                const targetId = tab.dataset.target;
                
                tabs.forEach(t => t.classList.remove("feedback-tab--active"));
                contents.forEach(c => {
                    c.classList.remove("feedback-tab-content--active");
                    c.style.display = "none";
                });

                tab.classList.add("feedback-tab--active");
                const targetContent = document.getElementById(targetId);
                if (targetContent) {
                    targetContent.classList.add("feedback-tab-content--active");
                    targetContent.style.display = "block";
                    targetContent.style.animation = "fade-in 0.3s ease";
                }
            });
        });
    }

    /* ───────────────────────────────────────────
       14. Markdown Parsing
    ─────────────────────────────────────────── */
    function initMarkdownParsing() {
        if (typeof marked === 'undefined') return;
        
        // Configure marked to not sanitize here as it might strip good HTML,
        // but be careful with XSS if user inputs are rendered raw.
        // We trust the AI output.
        marked.setOptions({
            breaks: true,
            gfm: true
        });

        const proseElements = document.querySelectorAll(".markdown-prose");
        proseElements.forEach(el => {
            const rawText = el.textContent;
            if (rawText.trim()) {
                el.innerHTML = marked.parse(rawText);
            }
        });
    }
})();
