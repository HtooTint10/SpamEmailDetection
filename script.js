
document.addEventListener("DOMContentLoaded", function () {

    const navLinks = document.querySelectorAll(".nav-link");
    const sections = document.querySelectorAll("section[id]");

    // ==========================================
    // CLICK NAVIGATION
    // ==========================================
    navLinks.forEach(link => {

        link.addEventListener("click", function () {

            navLinks.forEach(item => {
                item.classList.remove("active");
            });

            this.classList.add("active");

        });

    });


    // ==========================================
    // CHANGE ACTIVE NAVBAR WHEN SCROLLING
    // ==========================================
    function updateActiveNav() {

        let currentSection = "";

        const scrollPosition = window.scrollY + 200;

        sections.forEach(section => {

            const sectionTop = section.offsetTop;
            const sectionBottom = sectionTop + section.offsetHeight;

            if (
                scrollPosition >= sectionTop &&
                scrollPosition < sectionBottom
            ) {
                currentSection = section.id;
            }

        });


        // ==========================================
        // IMPORTANT:
        // If user reaches the bottom of the page,
        // automatically activate How It Works
        // ==========================================
        if (
            window.innerHeight + window.scrollY >=
            document.documentElement.scrollHeight - 10
        ) {
            currentSection = "how-it-works";
        }


        navLinks.forEach(link => {

            link.classList.remove("active");

            if (link.getAttribute("href") === "#" + currentSection) {
                link.classList.add("active");
            }

        });

    }


    // Run when scrolling
    window.addEventListener("scroll", updateActiveNav);

    // Run when page loads
    updateActiveNav();

});

