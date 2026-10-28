// تبدیل تاریخ میلادی به شمسی
function toJalali(gy, gm, gd) {
    var g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    var jy = (gy <= 1600) ? 0 : 979;
    gy -= (gy <= 1600) ? 621 : 1600;
    var gy2 = (gm > 2) ? (gy + 1) : gy;
    var days = 365 * gy + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100)
             + Math.floor((gy2 + 399) / 400) - 80 + gd + g_d_m[gm - 1];
    jy += 33 * Math.floor(days / 12053);
    days %= 12053;
    jy += 4 * Math.floor(days / 1461);
    days %= 1461;
    if (days > 365) {
        jy += Math.floor((days - 1) / 365);
        days = (days - 1) % 365;
    }
    var jm = (days < 186) ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
    var jd = 1 + ((days < 186) ? (days % 31) : ((days - 186) % 30));
    return [jy, jm, jd];
}

// فرمت کردن تاریخ شمسی
function formatJalaliDate(isoString) {
    if (!isoString) return '-';
    try {
        var d = new Date(isoString);
        if (isNaN(d.getTime())) return isoString;
        var j = toJalali(d.getFullYear(), d.getMonth() + 1, d.getDate());
        var h = d.getHours().toString().padStart(2, '0');
        var m = d.getMinutes().toString().padStart(2, '0');
        return j[0] + '/' + j[1].toString().padStart(2, '0') + '/' + j[2].toString().padStart(2, '0')
             + ' - ' + h + ':' + m;
    } catch(e) {
        return isoString;
    }
}

// تبدیل تمام عناصر با کلاس jalali-date
function convertAllDates() {
    document.querySelectorAll('.jalali-date').forEach(function(el) {
        var iso = el.getAttribute('data-iso');
        if (iso) el.textContent = formatJalaliDate(iso);
    });
}

// اجرای خودکار پس از بارگذاری صفحه
document.addEventListener('DOMContentLoaded', convertAllDates);
