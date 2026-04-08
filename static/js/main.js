// Booking form Alpine.js component
function bookingForm(houseId = '') {
    return {
        formData: {
            house: houseId || '',
            name: '',
            phone: '',
            check_in: '',
            check_out: '',
            guests: 2,
            message: ''
        },
        loading: false,
        success: false,
        error: false,
        successMessage: '',
        errorMessage: '',

        async submitForm() {
            this.loading = true;
            this.success = false;
            this.error = false;

            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            const formBody = new URLSearchParams();

            for (const [key, value] of Object.entries(this.formData)) {
                if (value !== '' && value !== null) {
                    formBody.append(key, value);
                }
            }

            try {
                const response = await fetch('/booking/create/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: formBody.toString()
                });

                const data = await response.json();

                if (data.success) {
                    this.success = true;
                    this.successMessage = data.message;
                    this.formData = {
                        house: houseId || '',
                        name: '',
                        phone: '',
                        check_in: '',
                        check_out: '',
                        guests: 2,
                        message: ''
                    };
                } else {
                    this.error = true;
                    if (data.errors) {
                        const firstError = Object.values(data.errors)[0];
                        this.errorMessage = Array.isArray(firstError) ? firstError[0] : firstError;
                    } else {
                        this.errorMessage = 'Произошла ошибка. Попробуйте ещё раз.';
                    }
                }
            } catch (e) {
                this.error = true;
                this.errorMessage = 'Ошибка соединения. Проверьте интернет и попробуйте ещё раз.';
            }

            this.loading = false;

            // Re-init lucide icons after Alpine updates DOM
            setTimeout(() => { if (window.lucide) lucide.createIcons(); }, 100);
        }
    };
}

// Booking calendar + price calculator
function bookingCalendar(initialHouseId = '') {
    return {
        houseId: initialHouseId,
        currentMonth: new Date().getMonth(),
        currentYear: new Date().getFullYear(),
        bookedDates: new Set(),
        prices: {},
        holidays: {},
        checkIn: null,
        checkOut: null,
        hoverDate: null,
        loading: false,
        breakdown: null,
        totalPrice: 0,
        totalNights: 0,
        hasConflict: false,
        // Form
        formData: { name: '', phone: '', guests: 2, message: '' },
        formLoading: false,
        formSuccess: false,
        formError: false,
        formMessage: '',

        async init() {
            if (this.houseId) await this.fetchData();
        },

        async selectHouse(id) {
            this.houseId = id;
            this.checkIn = null;
            this.checkOut = null;
            this.breakdown = null;
            await this.fetchData();
        },

        async fetchData() {
            if (!this.houseId) return;
            this.loading = true;
            try {
                const res = await fetch(`/api/calendar/${this.houseId}/?months=4`);
                const data = await res.json();
                this.bookedDates = new Set(data.booked_dates);
                this.prices = data.prices;
                this.holidays = data.holidays;
            } catch (e) { console.error(e); }
            this.loading = false;
        },

        // Calendar grid helpers
        get daysOfWeek() { return ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']; },

        get calendarMonths() {
            const months = [];
            for (let i = 0; i < 2; i++) {
                let m = this.currentMonth + i;
                let y = this.currentYear;
                if (m > 11) { m -= 12; y++; }
                months.push({ month: m, year: y });
            }
            return months;
        },

        monthName(m, y) {
            return new Date(y, m).toLocaleString('ru', { month: 'long', year: 'numeric' });
        },

        daysInMonth(m, y) {
            return new Date(y, m + 1, 0).getDate();
        },

        firstDayOfWeek(m, y) {
            const d = new Date(y, m, 1).getDay();
            return d === 0 ? 6 : d - 1; // Monday=0
        },

        dateStr(y, m, d) {
            return `${y}-${String(m+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        },

        isPast(ds) {
            return ds < new Date().toISOString().slice(0, 10);
        },

        isBooked(ds) { return this.bookedDates.has(ds); },
        isWeekend(ds) { const d = new Date(ds); return d.getDay() === 0 || d.getDay() === 6; },
        isHoliday(ds) { return ds in this.holidays; },

        isSelected(ds) { return ds === this.checkIn || ds === this.checkOut; },

        isInRange(ds) {
            if (!this.checkIn) return false;
            const end = this.checkOut || this.hoverDate;
            if (!end) return false;
            return ds > this.checkIn && ds < end;
        },

        hasBookedInRange(start, end) {
            let d = new Date(start);
            const e = new Date(end);
            while (d < e) {
                const s = d.toISOString().slice(0,10);
                if (this.bookedDates.has(s)) return true;
                d.setDate(d.getDate() + 1);
            }
            return false;
        },

        selectDate(ds) {
            if (this.isPast(ds) || this.isBooked(ds)) return;

            if (!this.checkIn || (this.checkIn && this.checkOut)) {
                // Start new selection
                this.checkIn = ds;
                this.checkOut = null;
                this.breakdown = null;
            } else {
                // Set end date
                if (ds <= this.checkIn) {
                    this.checkIn = ds;
                    return;
                }
                if (this.hasBookedInRange(this.checkIn, ds)) {
                    // Can't span across booked dates
                    this.checkIn = ds;
                    this.checkOut = null;
                    return;
                }
                this.checkOut = ds;
                this.calculatePrice();
            }
        },

        async calculatePrice() {
            if (!this.houseId || !this.checkIn || !this.checkOut) return;
            try {
                const res = await fetch(`/api/price/?house_id=${this.houseId}&check_in=${this.checkIn}&check_out=${this.checkOut}`);
                const data = await res.json();
                this.breakdown = data.breakdown;
                this.totalPrice = data.total_price;
                this.totalNights = data.total_nights;
                this.hasConflict = data.has_conflict;
            } catch (e) { console.error(e); }
        },

        prevMonth() {
            this.currentMonth--;
            if (this.currentMonth < 0) { this.currentMonth = 11; this.currentYear--; }
        },

        nextMonth() {
            this.currentMonth++;
            if (this.currentMonth > 11) { this.currentMonth = 0; this.currentYear++; }
        },

        canGoPrev() {
            const now = new Date();
            return this.currentYear > now.getFullYear() || (this.currentYear === now.getFullYear() && this.currentMonth > now.getMonth());
        },

        getPrice(ds) {
            return this.prices[ds] || null;
        },

        formatPrice(p) {
            if (!p) return '';
            return p >= 1000 ? Math.round(p/1000) + 'к' : p;
        },

        getDayClass(ds) {
            if (this.isPast(ds)) return 'text-stone-300 cursor-not-allowed';
            if (this.isBooked(ds)) return 'bg-stone-100 text-stone-300 line-through cursor-not-allowed';
            if (this.isSelected(ds)) return 'bg-forest-500 text-white font-bold rounded-xl';
            if (this.isInRange(ds)) return 'bg-forest-100 text-forest-700';
            if (this.isHoliday(ds)) return 'bg-red-50 text-red-600 hover:bg-red-100 cursor-pointer';
            if (this.isWeekend(ds)) return 'bg-amber-50 text-amber-700 hover:bg-amber-100 cursor-pointer';
            return 'hover:bg-forest-50 cursor-pointer text-stone-600';
        },

        // Form submit
        async submitBooking() {
            if (!this.houseId || !this.checkIn || !this.checkOut) return;
            this.formLoading = true;
            this.formSuccess = false;
            this.formError = false;

            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            const body = new URLSearchParams();
            body.append('house', this.houseId);
            body.append('check_in', this.checkIn);
            body.append('check_out', this.checkOut);
            body.append('name', this.formData.name);
            body.append('phone', this.formData.phone);
            body.append('guests', this.formData.guests);
            body.append('message', this.formData.message);

            try {
                const res = await fetch('/booking/create/', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: body.toString()
                });
                const data = await res.json();
                if (data.success) {
                    this.formSuccess = true;
                    this.formMessage = data.message;
                } else {
                    this.formError = true;
                    const errs = data.errors;
                    if (errs && errs.__all__) this.formMessage = errs.__all__[0];
                    else if (errs) this.formMessage = Object.values(errs)[0][0];
                    else this.formMessage = 'Произошла ошибка';
                }
            } catch (e) {
                this.formError = true;
                this.formMessage = 'Ошибка соединения';
            }
            this.formLoading = false;
            setTimeout(() => { if (window.lucide) lucide.createIcons(); }, 100);
        }
    };
}

// Weather widget — free Open-Meteo API (no key needed)
function weatherWidget() {
    return {
        temp: '--°С',
        desc: 'Загрузка...',
        async fetchWeather() {
            try {
                const res = await fetch('https://api.open-meteo.com/v1/forecast?latitude=43.96&longitude=40.88&current_weather=true&timezone=Europe/Moscow');
                const data = await res.json();
                const w = data.current_weather;
                this.temp = (w.temperature > 0 ? '+' : '') + Math.round(w.temperature) + '°С';
                const codes = {0:'Ясно',1:'Малооблачно',2:'Переменная облачность',3:'Пасмурно',
                    45:'Туман',51:'Морось',61:'Небольшой дождь',63:'Дождь',65:'Сильный дождь',
                    71:'Небольшой снег',73:'Снег',75:'Сильный снег',80:'Ливень',95:'Гроза'};
                this.desc = codes[w.weathercode] || 'Облачно';
            } catch(e) {
                this.temp = '--°С';
                this.desc = 'Нет данных';
            }
            this.$nextTick(() => { if (window.lucide) lucide.createIcons(); });
        }
    };
}

// Activity carousel
function activityCarousel() {
    return {
        current: 0,
        offset: 0,
        cardWidth: 0,
        gap: 20,
        total: 0,
        dragging: false,
        startX: 0,
        startOffset: 0,

        init() {
            this.$nextTick(() => {
                const track = this.$refs.track;
                if (!track) return;
                const cards = track.children;
                this.total = cards.length;
                if (this.total > 0) {
                    this.cardWidth = cards[0].offsetWidth;
                }
                // Handle resize
                window.addEventListener('resize', () => {
                    if (this.total > 0) {
                        this.cardWidth = track.children[0].offsetWidth;
                        this.goTo(this.current);
                    }
                });
                // Mouse/touch end listeners
                window.addEventListener('mouseup', () => this.endDrag());
                window.addEventListener('mousemove', (e) => this.onDrag(e));
                window.addEventListener('touchend', () => this.endDrag());
                window.addEventListener('touchmove', (e) => this.onDrag(e), { passive: true });
            });
        },

        next() {
            if (this.current < this.total - 1) {
                this.goTo(this.current + 1);
            } else {
                this.goTo(0);
            }
        },

        prev() {
            if (this.current > 0) {
                this.goTo(this.current - 1);
            } else {
                this.goTo(this.total - 1);
            }
        },

        goTo(index) {
            this.current = index;
            this.offset = index * (this.cardWidth + this.gap);
        },

        startDrag(e) {
            this.dragging = true;
            this.startX = e.type.includes('mouse') ? e.clientX : e.touches[0].clientX;
            this.startOffset = this.offset;
            this.$refs.track.style.cursor = 'grabbing';
            this.$refs.track.style.transition = 'none';
        },

        onDrag(e) {
            if (!this.dragging) return;
            const x = e.type.includes('mouse') ? e.clientX : e.touches[0].clientX;
            const diff = this.startX - x;
            this.offset = Math.max(0, this.startOffset + diff);
        },

        endDrag() {
            if (!this.dragging) return;
            this.dragging = false;
            this.$refs.track.style.cursor = 'grab';
            this.$refs.track.style.transition = '';
            // Snap to nearest card
            const nearest = Math.round(this.offset / (this.cardWidth + this.gap));
            this.goTo(Math.min(Math.max(nearest, 0), this.total - 1));
        }
    };
}

// Hero spotlight effect — light circle follows mouse
document.addEventListener('DOMContentLoaded', () => {
    const spotlight = document.getElementById('hero-spotlight');
    if (spotlight) {
        const section = spotlight.closest('section');
        section.addEventListener('mousemove', (e) => {
            const rect = section.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            spotlight.style.background =
                `radial-gradient(circle 350px at ${x}px ${y}px, rgba(255,255,255,0.15) 0%, transparent 40%, rgba(0,0,0,0.5) 100%)`;
        });
        section.addEventListener('mouseleave', () => {
            spotlight.style.background =
                'radial-gradient(circle 250px at 50% 50%, transparent 0%, rgba(0,0,0,0.4) 100%)';
        });
    }
});

// Firefly particles
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('fireflies');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let W, H, mouseX = -1, mouseY = -1;
    const particles = [];
    const COUNT = 25;

    function resize() {
        W = canvas.width = window.innerWidth;
        H = canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    // Track mouse
    window.addEventListener('mousemove', (e) => { mouseX = e.clientX; mouseY = e.clientY; });
    window.addEventListener('mouseleave', () => { mouseX = -1; mouseY = -1; });

    class Firefly {
        constructor() { this.reset(); }
        reset() {
            this.x = Math.random() * W;
            this.y = Math.random() * H;
            this.size = Math.random() * 2.5 + 1;
            this.speedX = (Math.random() - 0.5) * 0.4;
            this.speedY = (Math.random() - 0.5) * 0.4;
            this.opacity = 0;
            this.targetOpacity = Math.random() * 0.6 + 0.2;
            this.fadeSpeed = Math.random() * 0.008 + 0.003;
            this.glowing = true;
        }
        update() {
            // Drift
            this.x += this.speedX;
            this.y += this.speedY;
            // Slight attraction to mouse
            if (mouseX > 0) {
                const dx = mouseX - this.x, dy = mouseY - this.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 200) {
                    this.x += dx * 0.003;
                    this.y += dy * 0.003;
                    this.targetOpacity = 0.8;
                }
            }
            // Glow pulse
            if (this.glowing) {
                this.opacity += this.fadeSpeed;
                if (this.opacity >= this.targetOpacity) this.glowing = false;
            } else {
                this.opacity -= this.fadeSpeed;
                if (this.opacity <= 0) { this.reset(); this.glowing = true; }
            }
            // Wrap
            if (this.x < -10) this.x = W + 10;
            if (this.x > W + 10) this.x = -10;
            if (this.y < -10) this.y = H + 10;
            if (this.y > H + 10) this.y = -10;
        }
        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(180, 220, 140, ${this.opacity})`;
            ctx.fill();
            // Glow
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size * 3, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(180, 220, 140, ${this.opacity * 0.15})`;
            ctx.fill();
        }
    }

    for (let i = 0; i < COUNT; i++) particles.push(new Firefly());

    function animate() {
        ctx.clearRect(0, 0, W, H);
        particles.forEach(p => { p.update(); p.draw(); });
        requestAnimationFrame(animate);
    }
    animate();
});

// River line weaving between sections — hugs block edges
document.addEventListener('DOMContentLoaded', () => {
    const svg = document.getElementById('river-svg');
    const pathEl = document.getElementById('river-path');
    const pathThin = document.getElementById('river-path-thin');
    const container = document.getElementById('river-line');
    if (!svg || !pathEl || !container) return;

    function buildPath() {
        const sections = document.querySelectorAll('section[id]');
        if (sections.length < 2) return;

        const scrollTop = window.scrollY;
        const pageWidth = document.documentElement.clientWidth;
        const pageHeight = document.documentElement.scrollHeight;

        svg.setAttribute('viewBox', `0 0 ${pageWidth} ${pageHeight}`);
        svg.style.width = pageWidth + 'px';
        svg.style.height = pageHeight + 'px';
        container.style.height = pageHeight + 'px';

        // Find the max-w-7xl content box (1280px or less)
        const maxW = Math.min(1280, pageWidth - 32);
        const contentLeft = (pageWidth - maxW) / 2;
        const contentRight = contentLeft + maxW;

        // Line runs just outside content edges
        const leftX = contentLeft - 20;
        const rightX = contentRight + 20;
        const r = 30; // corner radius

        let d = '';
        let goLeft = true; // first section: line on left

        sections.forEach((sec, i) => {
            const rect = sec.getBoundingClientRect();
            const top = rect.top + scrollTop;
            const bottom = top + rect.height;
            const x = goLeft ? leftX : rightX;
            const nextX = goLeft ? rightX : leftX;

            if (i === 0) {
                // Start above first section
                d = `M ${x},${top - 100} L ${x},${bottom - r}`;
            } else {
                // Vertical line down the side of this section
                d += ` L ${x},${bottom - r}`;
            }

            // If not last section: corner + horizontal + corner to other side
            if (i < sections.length - 1) {
                const nextSec = sections[i + 1];
                const nextTop = nextSec.getBoundingClientRect().top + scrollTop;
                const gapMid = (bottom + nextTop) / 2;

                // Round corner down
                if (goLeft) {
                    d += ` Q ${x},${bottom} ${x + r},${bottom}`;
                    d += ` L ${nextX - r},${bottom}`;
                    d += ` Q ${nextX},${bottom} ${nextX},${bottom + r}`;
                } else {
                    d += ` Q ${x},${bottom} ${x - r},${bottom}`;
                    d += ` L ${nextX + r},${bottom}`;
                    d += ` Q ${nextX},${bottom} ${nextX},${bottom + r}`;
                }

                // Continue to next section top
                d += ` L ${nextX},${nextTop + r}`;
            } else {
                // Last section: extend down
                d += ` L ${x},${bottom + 100}`;
            }

            goLeft = !goLeft;
        });

        pathEl.setAttribute('d', d);
        pathThin.setAttribute('d', d);
    }

    buildPath();
    window.addEventListener('resize', buildPath);
    window.addEventListener('load', () => {
        buildPath();
        // Set up stroke-dasharray for draw-on-scroll
        const len = pathEl.getTotalLength();
        pathEl.style.strokeDasharray = len;
        pathEl.style.strokeDashoffset = len;
        pathThin.style.strokeDasharray = len;
        pathThin.style.strokeDashoffset = len;
        drawOnScroll();
    });

    function drawOnScroll() {
        const len = pathEl.getTotalLength();
        if (!len) return;
        const firstSection = document.querySelector('section[id]');
        window.addEventListener('scroll', () => {
            const scrollTop = window.scrollY;
            const start = firstSection ? firstSection.offsetTop - window.innerHeight * 0.5 : 0;
            const docHeight = document.documentElement.scrollHeight - window.innerHeight;
            const progress = Math.max(0, Math.min((scrollTop - start) / (docHeight - start), 1));
            const draw = len * (1 - progress);
            pathEl.style.strokeDashoffset = draw;
            pathThin.style.strokeDashoffset = draw;
        }, { passive: true });
    }
});

// Scroll reveal animations
document.addEventListener('DOMContentLoaded', () => {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.fade-up, .reveal, .reveal-scale').forEach(el => observer.observe(el));

    // Sticky mobile CTA — show after scrolling past hero
    const stickyCta = document.getElementById('sticky-cta');
    if (stickyCta) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > window.innerHeight) {
                stickyCta.classList.add('visible');
            } else {
                stickyCta.classList.remove('visible');
            }
        });
    }
});
