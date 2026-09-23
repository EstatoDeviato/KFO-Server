/*
 * Auto-expand the collapsible TOC branches around the heading currently being
 * read. Works together with overrides/partials/toc-item.html, which renders
 * headings with sub-headings as collapsible md-nav__item--nested branches.
 *
 * All TOC branches start collapsed. As you scroll, the branch(es) containing
 * the heading that enters the reading band open; a link arriving with a
 * #fragment, a mid-page hash change, or a click on any in-page anchor opens
 * the heading's branch immediately, so landing on (or jumping to)
 * `page/#some-heading` reveals the section that heading lives in. Branches
 * that were opened stay open, and a manual collapse is respected while that
 * heading stays in view (it only re-opens when the heading re-enters the band).
 */
(function (window, document) {
  "use strict";

  function onReady(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  onReady(function () {
    var tocRoot = document.querySelector(
      '[data-md-component="toc"]'
    );
    if (!tocRoot || !("IntersectionObserver" in window)) {
      return;
    }

    // Map heading ids -> their TOC links, in document order.
    var linkByHeadingId = {};
    var headingsInToc = [];
    tocRoot.querySelectorAll('a.md-nav__link[href^="#"]').forEach(function (link) {
      var id;
      try {
        id = decodeURIComponent(link.getAttribute("href").slice(1));
      } catch (err) {
        return;
      }
      var heading = document.getElementById(id);
      if (!heading) {
        return;
      }
      linkByHeadingId[id] = link;
      headingsInToc.push(heading);
    });
    if (!headingsInToc.length) {
      return;
    }

    // Open every ancestor branch of a TOC link so its heading becomes visible.
    function openBranch(link) {
      var item = link.closest("li.md-nav__item");
      while (item && tocRoot.contains(item)) {
        var input = item.querySelector(":scope > input.md-nav__toggle");
        if (input && !input.checked) {
          input.checked = true;
          var sub = item.querySelector(":scope > .md-nav");
          if (sub) {
            sub.setAttribute("aria-expanded", "true");
          }
        }
        item = item.parentElement.closest("li.md-nav__item");
      }
    }

    function openFor(id) {
      var link = linkByHeadingId[id];
      if (link) {
        openBranch(link);
      }
    }

    // If the page was loaded on (or jumped to) a heading, open its branch.
    function openHash() {
      if (!location.hash) {
        return;
      }
      var id;
      try {
        id = decodeURIComponent(location.hash.slice(1));
      } catch (err) {
        return;
      }
      setTimeout(openFor, 0, id);
    }
    window.addEventListener("hashchange", openHash);
    if (location.hash) {
      setTimeout(openHash, 0);
    }

    // Clicking any in-page anchor reveals the branch its heading lives in.
    // This covers content paragraph links and TOC links even when the hash
    // does not change (e.g. re-clicking the same link), which fires no
    // hashchange event. The browser still performs the normal anchor jump.
    document.addEventListener("click", function (ev) {
      var target = ev.target;
      if (!target || typeof target.closest !== "function") {
        return;
      }
      var link = target.closest('a[href^="#"]');
      if (!link) {
        return;
      }
      var id;
      try {
        id = decodeURIComponent(link.getAttribute("href").slice(1));
      } catch (err) {
        return;
      }
      if (id && linkByHeadingId[id]) {
        openBranch(linkByHeadingId[id]);
      }
    });

    // When a heading scrolls into the reading band, open its branch.
    var observer = new IntersectionObserver(function (changes) {
      changes.forEach(function (change) {
        if (change.isIntersecting) {
          openFor(change.target.id);
        }
      });
    }, { rootMargin: "-30% 0px -60% 0px" });

    headingsInToc.forEach(function (heading) {
      observer.observe(heading);
    });
  });
})(window, document);