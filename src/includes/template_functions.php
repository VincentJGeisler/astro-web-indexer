<?php
// Helper function for table sorting icon
function echoIcon(string $column, string $sortBy, string $sortOrder): void {
    if ($sortBy === $column) {
        echo $sortOrder === 'ASC' ? ' ▲' : ' ▼';
    }
}

// Helper function for generating pagination links
function getPaginationLink(array $query, int $pageNum, string $text, string $classes = ''): string {
    $query['page'] = $pageNum;
    $queryString = http_build_query($query);
    return '<a href="?' . $queryString . '" class="flex items-center justify-center px-3 h-8 leading-tight text-blue-300 bg-gray-700 border border-gray-600 rounded-lg hover:bg-gray-600 hover:text-white ' . $classes . '">' . $text . '</a>';
}

/**
 * Generates HTML markup for moon phase emoji with a tooltip.
 */
function getMoonPhaseMarkup(?float $angle, ?float $phase): string {
    if ($angle === null || $phase === null) return '<span>N/A</span>';

    if ($angle >= 337.5 || $angle < 22.5) $emoji = '🌑';
    elseif ($angle < 67.5) $emoji = '🌒';
    elseif ($angle < 112.5) $emoji = '🌓';
    elseif ($angle < 157.5) $emoji = '🌔';
    elseif ($angle < 202.5) $emoji = '🌕';
    elseif ($angle < 247.5) $emoji = '🌖';
    elseif ($angle < 292.5) $emoji = '🌗';
    else $emoji = '🌘';
    
    return "<div class=\"flex flex-col items-center gap-2\"><span title=\"" . number_format($angle, 0) . "°\">{$emoji}</span><span class=\"text-xs\">" . number_format($phase, 0) . "%</span></div>";
}

/**
 * Renders a table header with a translated label and a tooltip.
 *
 * @param string $sortKey The key for sorting (DB column name).
 * @param string $labelKey The key for translation.
 * @param string $sortBy Current sort column.
 * @param string $sortOrder Current sort order.
 * @param bool|null $isCalculated True for calculated, false for FITS header, null for general.
 */
function render_header_with_tooltip(string $sortKey, string $labelKey, string $sortBy, string $sortOrder, ?bool $isCalculated = null): void {
    $label = __($labelKey);
    $tooltip = '';

    if ($isCalculated === true) {
        $tooltip = __('calculated_by_app');
    } elseif ($isCalculated === false) {
        $tooltip = '[ ' . strtoupper($sortKey) . ' ]';
    }

    $titleAttribute = $tooltip ? ' title="' . htmlspecialchars($tooltip) . '"' : '';

    echo '<th class="p-3 whitespace-nowrap cursor-pointer hover:bg-gray-600"' . $titleAttribute . ' onclick="sortTable(\'' . htmlspecialchars($sortKey) . '\')">';
    echo htmlspecialchars($label);
    echoIcon($sortKey, $sortBy, $sortOrder);
    echo '</th>';
}

/**
 * Format a right ascension in degrees as HH:MM:SS.ss.
 */
function formatRaDegToHms($deg): string {
    if ($deg === null || $deg === '') return '';
    $hours = fmod((float)$deg, 360) / 15.0;
    if ($hours < 0) $hours += 24;
    $h = (int)floor($hours);
    $m = (int)floor(($hours - $h) * 60);
    $s = ($hours - $h - $m / 60) * 3600;
    return sprintf('%02dh%02dm%05.2fs', $h, $m, $s);
}

/**
 * Format a declination in degrees as +/-DD:MM:SS.s.
 */
function formatDecDegToDms($deg): string {
    if ($deg === null || $deg === '') return '';
    $deg = (float)$deg;
    $sign = $deg < 0 ? '-' : '+';
    $abs = abs($deg);
    $d = (int)floor($abs);
    $m = (int)floor(($abs - $d) * 60);
    $s = ($abs - $d - $m / 60) * 3600;
    return $sign . sprintf('%02d°%02d\'%04.1f"', $d, $m, $s);
}

/**
 * Translated label for a solve_status value.
 */
function solveStatusLabel(string $status): string {
    $map = [
        'pending'      => 'solve_status_pending',
        'solved'       => 'solve_status_solved',
        'failed'       => 'solve_status_failed',
        'skipped'      => 'solve_status_skipped',
        'no_star_db'   => 'solve_status_no_star_db',
    ];
    return __(isset($map[$status]) ? $map[$status] : ('solve_status_' . $status));
}

/**
 * Renders the identified-object cell: primary_object (link-style) with a
 * tooltip containing the full solve info, a status-coloured dot, and a small
 * "header: X" badge when the header object disagrees with the solve.
 */
function getIdentifiedObjectMarkup(array $f): string {
    $status = (string)($f['solve_status'] ?? '');
    $primary = $f['primary_object'] ?? null;

    // status dot colour
    $dotColor = match ($status) {
        'solved'     => 'bg-green-500',
        'pending'    => 'bg-yellow-500',
        'failed'     => 'bg-red-500',
        'no_star_db' => 'bg-purple-500',
        default      => 'bg-gray-600',
    };

    // tooltip with full solve details
    $tip = [];
    $tip[] = __('solve_status') . ': ' . solveStatusLabel($status ?: 'pending');
    if (!empty($f['solved_ra']))  $tip[] = __('solved_ra') . ': ' . formatRaDegToHms($f['solved_ra']);
    if (!empty($f['solved_dec'])) $tip[] = __('solved_dec') . ': ' . formatDecDegToDms($f['solved_dec']);
    if (isset($f['solved_pixscale']) && $f['solved_pixscale'] !== null && $f['solved_pixscale'] !== '') {
        $tip[] = __('solved_pixscale') . ': ' . number_format((float)$f['solved_pixscale'], 3) . '"/px';
    }
    if (isset($f['solved_rotation']) && $f['solved_rotation'] !== null && $f['solved_rotation'] !== '') {
        $tip[] = __('solved_rotation') . ': ' . number_format((float)$f['solved_rotation'], 2) . '°';
    }
    if (!empty($f['matched_objects'])) $tip[] = __('matched_objects') . ': ' . $f['matched_objects'];
    $tooltip = htmlspecialchars(implode("\n", $tip));

    $html = '<span class="inline-flex items-center gap-1.5" title="' . $tooltip . '" style="white-space:pre-line;">';
    $html .= '<span class="w-2 h-2 rounded-full inline-block ' . $dotColor . '"></span>';

    if ($primary) {
        $html .= '<span class="text-gray-100">' . htmlspecialchars($primary) . '</span>';
    } else {
        $html .= '<span class="text-gray-500 text-xs">' . htmlspecialchars(solveStatusLabel($status ?: 'pending')) . '</span>';
    }
    $html .= '</span>';

    // "header: X" badge when the header object disagrees with the solve
    $headerObj = trim((string)($f['object'] ?? ''));
    if ($primary && $headerObj !== '') {
        $normHeader = mb_strtolower($headerObj);
        $normPrimary = mb_strtolower((string)$primary);
        $matched = array_filter(array_map('trim', explode(',', (string)($f['matched_objects'] ?? ''))));
        $matchedLower = array_map('mb_strtolower', $matched);
        if ($normHeader !== $normPrimary && !in_array($normHeader, $matchedLower, true)) {
            $html .= '<span class="ml-1 text-[10px] px-1 py-0.5 rounded bg-gray-700 text-gray-400" title="' . htmlspecialchars(__('header_object_tooltip')) . '">'
                . htmlspecialchars(__('header_object')) . ': ' . htmlspecialchars($headerObj) . '</span>';
        }
    }

    return $html;
}

?>