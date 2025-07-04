# Quick fix for pos_order_views.xml specifically
$file = "views\pos_order_views.xml"

if (Test-Path $file) {
    Write-Host "Fixing $file..." -ForegroundColor Cyan
    
    $content = Get-Content $file -Raw -Encoding UTF8
    $originalContent = $content
    
    # Count modifiers before
    $modifiersBefore = ([regex]::Matches($content, 'modifiers\s*=')).Count
    Write-Host "Found $modifiersBefore modifiers attributes" -ForegroundColor Yellow
    
    # Specific replacements for pos_order_views.xml
    $replacements = @(
        @{
            Find = 'modifiers="{''invisible'': [(''can_send_fel'', ''='', False)]}"'
            Replace = 'invisible="can_send_fel == False"'
        },
        @{
            Find = 'modifiers="{''invisible'': [(''fel_status'', ''!='', ''error'')]}"'
            Replace = 'invisible="fel_status != ''error''"'
        },
        @{
            Find = 'modifiers="{''invisible'': [''|'', (''can_send_fel'', ''='', False), (''fel_status'', ''in'', [''certified'', ''sending''])]}"'
            Replace = 'invisible="can_send_fel == False or fel_status in [''certified'', ''sending'']"'
        },
        @{
            Find = 'modifiers="{''invisible'': [(''fel_document_id'', ''='', False)]}"'
            Replace = 'invisible="fel_document_id == False"'
        },
        @{
            Find = 'modifiers="{''invisible'': [(''requires_fel'', ''='', False)]}"'
            Replace = 'invisible="requires_fel == False"'
        },
        @{
            Find = 'modifiers="{''invisible'': [(''fel_uuid'', ''='', False)]}"'
            Replace = 'invisible="fel_uuid == False"'
        },
        @{
            Find = 'modifiers="{''invisible'': [(''fel_error_message'', ''='', False)]}"'
            Replace = 'invisible="fel_error_message == False"'
        },
        @{
            Find = 'modifiers="{''invisible'': [(''fel_certification_date'', ''='', False)]}"'
            Replace = 'invisible="fel_certification_date == False"'
        },
        @{
            Find = 'modifiers="{''invisible'': [(''use_fel'', ''='', False)]}"'
            Replace = 'invisible="use_fel == False"'
        },
        @{
            Find = 'modifiers="{''invisible'': [(''session_id.config_id.is_restaurant'', ''='', False)]}"'
            Replace = 'invisible="session_id.config_id.is_restaurant == False"'
        },
        @{
            Find = 'modifiers="{''invisible'': [(''is_restaurant'', ''='', False)]}"'
            Replace = 'invisible="is_restaurant == False"'
        },
        @{
            Find = 'modifiers="{''readonly'': [(''fel_status'', ''in'', [''certified'', ''sending''])]}"'
            Replace = 'readonly="fel_status in [''certified'', ''sending'']"'
        }
    )
    
    # Apply replacements
    $changeCount = 0
    foreach ($replacement in $replacements) {
        if ($content -like "*$($replacement.Find)*") {
            $content = $content.Replace($replacement.Find, $replacement.Replace)
            Write-Host "  ✓ Fixed: $($replacement.Find.Substring(0, [Math]::Min(60, $replacement.Find.Length)))..." -ForegroundColor Green
            $changeCount++
        }
    }
    
    # Save if changed
    if ($content -ne $originalContent) {
        Set-Content -Path $file -Value $content -Encoding UTF8 -NoNewline
        Write-Host "`nSaved $changeCount fixes to $file" -ForegroundColor Green
    } else {
        Write-Host "No changes needed" -ForegroundColor Yellow
    }
    
    # Count modifiers after
    $modifiersAfter = ([regex]::Matches($content, 'modifiers\s*=')).Count
    if ($modifiersAfter -gt 0) {
        Write-Host "`nStill $modifiersAfter modifiers remaining - checking what they are:" -ForegroundColor Red
        
        $lines = $content -split "`n"
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match 'modifiers\s*=') {
                Write-Host "  Line $($i+1): $($lines[$i].Trim())" -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "✓ All modifiers in pos_order_views.xml have been fixed!" -ForegroundColor Green
    }
} else {
    Write-Host "File not found: $file" -ForegroundColor Red
}

# Now run the fix for other remaining files
Write-Host "`n=== Fixing Other Remaining Complex Modifiers ===" -ForegroundColor Cyan

$otherFixes = @{
    "views\fel_document_type_views.xml" = @(
        @{ Find = 'modifiers="{''invisible'': [(''document_count'', ''>'', 0)]}"'; Replace = 'invisible="document_count > 0"' }
    )
    "views\pos_config_views.xml" = @(
        @{ Find = 'modifiers="{''invisible'': [(''use_fel'', ''='', False)], ''required'': [(''use_fel'', ''='', True)]}"'; Replace = 'invisible="use_fel == False" required="use_fel == True"' }
    )
    "wizard\fel_document_send_views.xml" = @(
        @{ Find = 'modifiers="{''invisible'': [(''invalid_documents'', ''='', 0)]}"'; Replace = 'invisible="invalid_documents == 0"' }
        @{ Find = 'modifiers="{''invisible'': [(''loaded_invoice_ids'', ''='', [])]}"'; Replace = 'invisible="not loaded_invoice_ids"' }
        @{ Find = 'modifiers="{''invisible'': [(''loaded_order_ids'', ''='', [])]}"'; Replace = 'invisible="not loaded_order_ids"' }
        @{ Find = 'modifiers="{''invisible'': [(''orders_without_customer'', ''='', 0)]}"'; Replace = 'invisible="orders_without_customer == 0"' }
    )
    "wizard\fel_nit_verification_wizard_views.xml" = @(
        @{ Find = 'modifiers="{''required'': [(''create_partner'', ''='', True), (''partner_id'', ''='', False)]}"'; Replace = 'required="create_partner == True and partner_id == False"' }
    )
}

foreach ($file in $otherFixes.Keys) {
    if (Test-Path $file) {
        Write-Host "`nProcessing: $file" -ForegroundColor Yellow
        $content = Get-Content $file -Raw -Encoding UTF8
        $originalContent = $content
        
        foreach ($fix in $otherFixes[$file]) {
            $pattern = [regex]::Escape($fix.Find)
            if ($content -match $pattern) {
                $content = $content -replace $pattern, $fix.Replace
                Write-Host "  ✓ Fixed modifier" -ForegroundColor Green
            }
        }
        
        if ($content -ne $originalContent) {
            Set-Content -Path $file -Value $content -Encoding UTF8 -NoNewline
        }
    }
}

Write-Host "`n=== Final Check ===" -ForegroundColor Cyan
$remainingCount = 0
Get-ChildItem -Path . -Filter "*.xml" -Recurse | Where-Object { $_.FullName -notlike "*backup*" } | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $matches = [regex]::Matches($content, 'modifiers\s*=')
    if ($matches.Count -gt 0) {
        $remainingCount += $matches.Count
    }
}

if ($remainingCount -eq 0) {
    Write-Host "✓ SUCCESS! All modifiers have been fixed!" -ForegroundColor Green
    Write-Host "`nYou can now:" -ForegroundColor Cyan
    Write-Host "1. git add -A" -ForegroundColor White
    Write-Host "2. git commit -m 'Fix all modifiers syntax for Odoo 17 compatibility'" -ForegroundColor White
    Write-Host "3. git push" -ForegroundColor White
} else {
    Write-Host "Found $remainingCount modifiers still remaining" -ForegroundColor Red
}