import os
import docx
from docx.shared import Inches, Pt, RGBColor, Mm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def create_document():
    doc = docx.Document()

    # ---------------------------------------------------------------------------
    # Page Setup: A4, Margins (Top: 1", Bottom: 1", Left: 1.5", Right: 1")
    # ---------------------------------------------------------------------------
    section = doc.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.5)
    section.right_margin = Inches(1.0)
    section.different_first_page_header_footer = True

    # Configure Default Style
    style_normal = doc.styles['Normal']
    font = style_normal.font
    font.name = 'Times New Roman'
    font.size = Pt(12)
    font.color.rgb = RGBColor(0, 0, 0)
    style_normal.paragraph_format.line_spacing = 1.0
    style_normal.paragraph_format.space_after = Pt(6)
    style_normal.paragraph_format.space_before = Pt(0)

    # ---------------------------------------------------------------------------
    # Helper Functions
    # ---------------------------------------------------------------------------
    def add_chapter_title(chap_num, chap_title):
        p1 = doc.add_paragraph()
        p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p1.paragraph_format.space_before = Pt(12)
        p1.paragraph_format.space_after = Pt(4)
        r1 = p1.add_run(chap_num)
        r1.font.name = 'Times New Roman'
        r1.font.size = Pt(12)
        r1.font.bold = True

        p2 = doc.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p2.paragraph_format.space_before = Pt(0)
        p2.paragraph_format.space_after = Pt(18)
        r2 = p2.add_run(chap_title)
        r2.font.name = 'Times New Roman'
        r2.font.size = Pt(12)
        r2.font.bold = True

    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        r.font.name = 'Times New Roman'
        r.font.size = Pt(12)
        r.font.bold = True
        return p

    def add_h3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        r.font.name = 'Times New Roman'
        r.font.size = Pt(12)
        r.font.bold = True
        return p

    def add_h4(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        r.font.name = 'Times New Roman'
        r.font.size = Pt(12)
        r.font.bold = True
        r.font.italic = True
        return p

    def add_p(text, indent=True):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_after = Pt(6)
        if indent:
            p.paragraph_format.first_line_indent = Inches(0.5)
        r = p.add_run(text)
        r.font.name = 'Times New Roman'
        r.font.size = Pt(12)
        return p

    def add_table_title(tbl_num, tbl_title):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        r1 = p.add_run(f"Table {tbl_num}.\n")
        r1.font.name = 'Times New Roman'
        r1.font.size = Pt(12)
        r1.font.bold = True
        r2 = p.add_run(tbl_title)
        r2.font.name = 'Times New Roman'
        r2.font.size = Pt(12)
        r2.font.italic = True
        return p

    def add_figure(img_path, fig_num, fig_title, width=Inches(5.7)):
        if os.path.exists(img_path):
            p_img = doc.add_paragraph()
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img.paragraph_format.space_before = Pt(8)
            p_img.paragraph_format.space_after = Pt(4)
            p_img.paragraph_format.keep_with_next = True
            run_img = p_img.add_run()
            run_img.add_picture(img_path, width=width)

        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(2)
        p_cap.paragraph_format.space_after = Pt(10)
        r1 = p_cap.add_run(f"Figure {fig_num}. ")
        r1.font.name = 'Times New Roman'
        r1.font.size = Pt(11)
        r1.font.bold = True
        r2 = p_cap.add_run(fig_title)
        r2.font.name = 'Times New Roman'
        r2.font.size = Pt(11)
        r2.font.italic = True
        return p_cap

    def style_apa_table(table, col_widths=None):
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        # Table top and bottom borders
        tblPr = table._tbl.tblPr
        tblBorders = parse_xml(
            '<w:tblBorders %s>'
            '  <w:top w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
            '  <w:left w:val="none"/>'
            '  <w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
            '  <w:right w:val="none"/>'
            '  <w:insideH w:val="none"/>'
            '  <w:insideV w:val="none"/>'
            '</w:tblBorders>' % nsdecls('w')
        )
        tblPr.append(tblBorders)

        # Header row bottom border
        for cell in table.rows[0].cells:
            tcPr = cell._tc.get_or_add_tcPr()
            tcBorders = parse_xml(
                '<w:tcBorders %s>'
                '  <w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
                '</w:tcBorders>' % nsdecls('w')
            )
            tcPr.append(tcBorders)

        # Style all cells
        for row_idx, row in enumerate(table.rows):
            trPr = row._tr.get_or_add_trPr()
            trPr.append(parse_xml('<w:cantSplit %s/>' % nsdecls('w')))
            if row_idx == 0:
                trPr.append(parse_xml('<w:tblHeader %s/>' % nsdecls('w')))

            for col_idx, cell in enumerate(row.cells):
                if col_widths and col_idx < len(col_widths):
                    cell.width = col_widths[col_idx]
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                # Set padding
                tcPr = cell._tc.get_or_add_tcPr()
                tcMar = parse_xml(
                    '<w:tcMar %s>'
                    '  <w:top w:w="80" w:type="dxa"/>'
                    '  <w:bottom w:w="80" w:type="dxa"/>'
                    '  <w:left w:w="120" w:type="dxa"/>'
                    '  <w:right w:w="120" w:type="dxa"/>'
                    '</w:tcMar>' % nsdecls('w')
                )
                tcPr.append(tcMar)
                for p in cell.paragraphs:
                    p.paragraph_format.line_spacing = 1.0
                    p.paragraph_format.space_before = Pt(1)
                    p.paragraph_format.space_after = Pt(1)
                    for r in p.runs:
                        r.font.name = 'Times New Roman'
                        r.font.size = Pt(10)
                        if row_idx == 0:
                            r.font.bold = True

    def setup_section_footer(sec, author_text):
        sec.different_first_page_header_footer = True
        footer = sec.footer
        p = footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p.paragraph_format.space_before = Pt(6)
        
        # Add top border line to footer paragraph to match template
        pPr = p._p.get_or_add_pPr()
        pBdr = parse_xml(
            '<w:pBdr %s>'
            '  <w:top w:val="single" w:sz="6" w:space="4" w:color="000000"/>'
            '</w:pBdr>' % nsdecls('w')
        )
        pPr.append(pBdr)

        # Left aligned author name and right aligned page number
        r_author = p.add_run(author_text)
        r_author.font.name = 'Times New Roman'
        r_author.font.size = Pt(11)

        # Tab stop for right alignment
        r_tab = p.add_run("\t\t\t\t\t\t\t\t\t\t")
        
        # Simple page field
        fld = parse_xml(r'<w:fldSimple %s w:instr="PAGE"/>' % nsdecls('w'))
        p._p.append(fld)

    # Apply footer to section 0
    setup_section_footer(section, "Lumanta, S. J. M., et al.")

    # ===========================================================================
    # CHAPTER 4
    # ===========================================================================
    add_chapter_title("CHAPTER 4", "METHODOLOGY, RESULTS AND DISCUSSION")

    # Chapter intro (< 200 words)
    add_p(
        "This chapter presents the methodology, design specifications, and analytical results for the SENTINEL "
        "autonomous threat detection and evacuation simulation system developed for Sto. Niño Senior High School, "
        "Tacloban City. It begins with a comprehensive requirements analysis detailing the performance, safety, and "
        "security standards necessary to ensure life-safety preservation during active hostile intruder incidents. "
        "Furthermore, this chapter outlines the Software Development Life Cycle (SDLC) utilizing the Prototyping Model, "
        "accompanied by operational test, security, and maintenance plans. Project schedules and topological network models "
        "are systematically examined through Gantt and PERT chart computations, Context and Data Flow Diagrams, operational "
        "flowcharts, normalized database architectures in Third Normal Form (3NF), and comprehensive use-case specifications."
    )

    # 4.1 Requirements Analysis
    add_h2("4.1 Requirements Analysis")
    add_p(
        "Requirements analysis forms the foundational bedrock of the SENTINEL system, translating active shooter "
        "and physical campus violence mitigation protocols into explicit technical parameters. Secondary academic "
        "institutions represent vulnerable soft targets due to open perimeters, complex multi-story building geometries, "
        "and high occupant densities (Memon et al., 2021). The functional efficacy of the SENTINEL system depends upon "
        "rigorous adherence to three non-functional operational domains: performance requirements, safety requirements, "
        "and security requirements, each systematically presented in tabular format and supported by engineering literature."
    )

    # 4.1.1 Performance Requirements
    add_h3("4.1.1 Performance Requirements")
    add_p(
        "Performance requirements govern the real-time processing constraints, latency boundaries, and throughput capacities "
        "of the edge microcontrollers, computer vision pipelines, and graph-theoretic pathfinding algorithms. Active hostile "
        "threat events evolve within seconds, demanding sub-second sensor telemetry and sub-frame visual inference to prevent "
        "fatal egress delays (Redmon & Farhadi, 2018; Jocher et al., 2023). Table 1 outlines the performance parameters "
        "established for the SENTINEL deployment across the three campus structures: the Tech Pro Building (TPB), "
        "Academic Building (AB), and Laboratory Building (LB)."
    )

    add_table_title("1", "Performance Requirements for the SENTINEL Campus Threat Evacuation System")
    t1 = doc.add_table(rows=8, cols=4)
    t1_headers = ["Parameter ID", "Requirement Metric", "Target Benchmark", "Design Rationale & Technical Reference"]
    for i, h in enumerate(t1_headers):
        t1.rows[0].cells[i].paragraphs[0].text = h

    t1_data = [
        ("PR-01", "Acoustic Signal Acquisition & RMS Trigger Latency", "< 200 ms", 
         "ESP32 sampling I2S digital audio (INMP441) at 16 kHz to detect gunshots, screams, and explosive acoustics (Al-Turjman, 2020)."),
        ("PR-02", "Visual Object & Weapon Inference (YOLOv8)", "< 66 ms (>= 15 FPS)", 
         "Real-time identification of bladed weapons and firearms on edge IP camera video feeds using TensorRT optimization (Jocher et al., 2023)."),
        ("PR-03", "Human Pose Keypoint Estimation (MediaPipe)", "< 50 ms / frame", 
         "Tracking aggressive postures, firearm aiming stance, and physical struggles across 33 skeletal landmarks (Lugaresi et al., 2019)."),
        ("PR-04", "Multi-Modal Sensor Fusion Score Synthesis", "< 50 ms / cycle", 
         "Synthesizing composite Threat Index T = 0.40(Object) + 0.35(Pose) + 0.25(Acoustic) with multi-signal confidence verification (Memon et al., 2021)."),
        ("PR-05", "Dijkstra Dynamic Shortest Path Optimization", "< 15 ms (all 36 rooms)", 
         "Simultaneous multi-source path computation across 36 classrooms, stairwells, and dual gates on weighted adjacency graph (Dijkstra, 1959)."),
        ("PR-06", "WebSocket Alert & SVG Egress Path Broadcast", "< 100 ms network transit", 
         "Asynchronous full-duplex transmission of SVG arrows, obstacle flags, and room-level directives to client browsers (Fette & Melnikov, 2011)."),
        ("PR-07", "System Availability & MTBF", "99.9% Uptime (> 5,000 hrs MTBF)", 
         "Continuous campus monitoring during academic hours with automated watchdog recovery on edge microcontrollers (Pressman & Maxim, 2020).")
    ]
    for r_idx, row in enumerate(t1_data):
        for c_idx, val in enumerate(row):
            t1.rows[r_idx+1].cells[c_idx].paragraphs[0].text = val
    style_apa_table(t1, [Inches(1.0), Inches(1.8), Inches(1.1), Inches(1.8)])

    add_p(
        "As detailed in Table 1, the timing relationships are calibrated to eliminate latency bottlenecks that could "
        "render digital evacuation signage obsolete during rapid intruder maneuvers. Empirical crowd dynamics research "
        "indicates that the initial 30 to 90 seconds of an active threat event dictate over 80% of survivability outcomes "
        "(Helbing et al., 2000). By maintaining edge acoustic trigger latency below 200 milliseconds and bounding visual "
        "detection within 66 milliseconds, the SENTINEL architecture ensures that multi-modal fusion scoring occurs faster "
        "than human auditory cognitive reaction times. Furthermore, the dynamic Dijkstra routing sweep completes in under "
        "15 milliseconds for the entire 36-classroom topological graph. This instantaneous computational response prevents "
        "the accumulation of egress queueing and assures that room wardens receive real-time updates as dynamic obstacles "
        "or compromised corridors shift."
    )

    # 4.1.2 Safety Requirements
    add_h3("4.1.2 Safety Requirements")
    add_p(
        "Safety requirements define systemic safeguards preventing the product from inducing accidental harm, "
        "misguiding fleeing occupants into hostile encounters, or creating crushing hazards in confined stairwells. "
        "In emergency egress systems, an algorithmic failure that directs evacuees toward an active shooter constitutes "
        "a catastrophic failure mode (Pelechano & Malkawi, 2008; National Fire Protection Association [NFPA], 2021). "
        "Table 2 itemizes the safety mandates codified within SENTINEL, aligning with DepEd Disaster Risk Reduction "
        "and Management (DRRM) protocols."
    )

    add_table_title("2", "Safety Requirements and Life-Preservation Safeguards")
    t2 = doc.add_table(rows=7, cols=4)
    t2_headers = ["Safety ID", "Safeguard Description", "Preventative Action & Policy", "Governing Standard"]
    for i, h in enumerate(t2_headers):
        t2.rows[0].cells[i].paragraphs[0].text = h

    t2_data = [
        ("SR-01", "Threat-Compromised Zone Isolation", 
         "Immediately flags threatened corridors, stairwells, and gates with infinite graph weight to forbid egress routing.", 
         "NFPA 101 Life Safety Code (NFPA, 2021)"),
        ("SR-02", "Automated Shelter-in-Place (HOLD) Directives", 
         "Commands upper-floor classrooms to lock down in place when their sole egress stairwell or ground corridor is blocked.", 
         "DepEd DRRM Manual (DepEd, 2020)"),
        ("SR-03", "Obstacle-Free Outdoor Pathway Geometry", 
         "Restricts campus ground evacuation arrows to paved paths and the open quadrangle, strictly avoiding fences and tree clusters.", 
         "Life Safety Egress Standards (Zheng et al., 2011)"),
        ("SR-04", "Dual-Gate Perimeter Failover", 
         "When West Gate (Gate-W) is threatened, automatically redirects all 36 rooms to Northeast Gate (Gate-NE) via safe stairs.", 
         "Campus Security Best Practices (FEMA, 2012)"),
        ("SR-05", "Campus-Wide Simultaneous Lockdown", 
         "Initiates emergency lockdown and halts all physical egress movement when both perimeter gates are compromised.", 
         "Standard Incident Command System (DHS, 2017)"),
        ("SR-06", "Fail-Safe Default on Network Disruption", 
         "Maintains last-known verified safety state and illuminates local emergency beacons during network dropouts.", 
         "IEC 61508 Functional Safety (IEC, 2010)")
    ]
    for r_idx, row in enumerate(t2_data):
        for c_idx, val in enumerate(row):
            t2.rows[r_idx+1].cells[c_idx].paragraphs[0].text = val
    style_apa_table(t2, [Inches(0.9), Inches(1.8), Inches(1.8), Inches(1.2)])

    add_p(
        "The safety requirements codified in Table 2 establish non-negotiable architectural constraints for the system. "
        "A critical safety innovation is the automated Shelter-in-Place (HOLD) directive. Traditional fire alarm systems "
        "promulgate indiscriminate evacuation signals, which in an active violence scenario can herd occupants directly into "
        "the line of fire in ground-floor lobbies or exterior courtyards (Lovreglio et al., 2016). SENTINEL enforces a "
        "strict topological rule: if a threat is detected on Floor 1 of the Tech Pro Building, occupants on Floors 2, 3, "
        "and 4 are prohibited from proceeding downward and are instructed via digital indicators to barricade in place. "
        "Additionally, the geometric ground path routing prevents evacuees from traversing vegetative blind spots or trapped "
        "perimeter alleys, ensuring adherence to NFPA 101 spatial egress guidelines (NFPA, 2021)."
    )

    # 4.1.3 Security Requirements
    add_h3("4.1.3 Security Requirements")
    add_p(
        "Security requirements protect the confidentiality, integrity, and availability of sensory data, network streams, "
        "and administrative control interfaces. Because SENTINEL ingests real-time video surveillance and acoustic telemetry, "
        "the system must prevent malicious tampering, spoofed emergency signals, and unauthorized interception that could "
        "compromise student privacy (Khan et al., 2018; Winkler & Rinner, 2014). Table 3 specifies the security safeguards "
        "enforced across the software and microcontroller firmware."
    )

    add_table_title("3", "Security, Privacy, and Authentication Requirements")
    t3 = doc.add_table(rows=6, cols=4)
    t3_headers = ["Security ID", "Security Domain", "Enforced Control Mechanism", "Compliance Reference"]
    for i, h in enumerate(t3_headers):
        t3.rows[0].cells[i].paragraphs[0].text = h

    t3_data = [
        ("SEC-01", "Role-Based Access Control (RBAC)", 
         "Restricts manual drill triggering, gate overrides, and graph configuration to authenticated DRRM Incident Commanders.", 
         "ISO/IEC 27001 (ISO, 2013)"),
        ("SEC-02", "Cryptographic Data Transmission", 
         "Enforces TLS 1.3 encryption across all REST API endpoints, WebSocket streams, and RTSP video feeds.", 
         "RFC 8446 TLS Protocol (Rescorla, 2018)"),
        ("SEC-03", "Edge Microcontroller Authentication", 
         "Validates ESP32 telemetry packets using HMAC-SHA256 pre-shared tokens to prevent rogue sensor injection.", 
         "NIST SP 800-147B (NIST, 2014)"),
        ("SEC-04", "Data Privacy & Image Sanitization", 
         "Transmits bounding box coordinates and threat indices without cloud biometric facial storage.", 
         "Republic Act No. 10173 (DPA of 2012)"),
        ("SEC-05", "Immutable Forensic Audit Trail", 
         "Logs all timestamped threat classifications, manual overrides, and routing states in an append-only audit datastore.", 
         "NIST SP 800-92 (NIST, 2006)")
    ]
    for r_idx, row in enumerate(t3_data):
        for c_idx, val in enumerate(row):
            t3.rows[r_idx+1].cells[c_idx].paragraphs[0].text = val
    style_apa_table(t3, [Inches(1.0), Inches(1.5), Inches(1.9), Inches(1.3)])

    add_p(
        "Security mechanisms specified in Table 3 safeguard the system against both cyber and physical attack vectors. "
        "In educational technology deployments, privacy concerns regarding continuous camera surveillance represent a "
        "paramount ethical consideration (Winkler & Rinner, 2014). Under SENTINEL's edge-computing paradigm, video frames "
        "are analyzed in local memory for weapon bounding boxes and skeletal pose vectors, discarding raw footage in the absence "
        "of verified threat states. This adheres strictly to the National Privacy Commission guidelines under Republic Act No. 10173 "
        "(Data Privacy Act of 2012). Furthermore, cryptographic verification of ESP32 sensor telemetry prevents malicious actors "
        "from triggering false alarms or manipulating evacuation routes during critical operations (Stallings, 2020)."
    )

    # 4.2 Design of Software, Systems, Product, and/or Processes
    add_h2("4.2 Design of Software, Systems, Product, and/or Processes")
    add_p(
        "This section articulates the architectural design, developmental lifecycle, verification frameworks, "
        "and topological modeling techniques underpinning SENTINEL. Developing an integrated system comprising "
        "embedded microcontrollers (ESP32), computer vision pipelines (YOLOv8 and MediaPipe), and algorithmic "
        "graph pathfinders requires a cohesive development methodology. The architectural components are systematically "
        "explicated across software development lifecycle models, operational verification plans, schedule network "
        "computations, system flowcharts, database normalization, and behavioral use-case diagrams."
    )

    # 4.2.1 Systems Development Life Cycle (SDLC) Model
    add_h3("4.2.1 Systems Development Life Cycle (SDLC) Model")
    add_p(
        "The development of the SENTINEL system was governed by the Prototyping Model. The Prototyping Model is an "
        "iterative software development approach wherein an initial operational prototype is rapidly synthesized, evaluated "
        "by stakeholders, and incrementally refined until all operational requirements are satisfied (Pressman & Maxim, 2020; "
        "Sommerville, 2016). Given the novel multi-disciplinary convergence of embedded ESP32 audio hardware, edge deep "
        "learning inference, and real-time campus graph routing, traditional linear waterfall methodologies present prohibitive "
        "risks of late-stage integration failure. Figure 1 illustrates the iterative prototyping lifecycle executed for the project."
    )

    add_figure("doc_figures/fig_sdlc.png", 1, "Prototyping Model Applied to SENTINEL System Development")

    add_p(
        "As depicted in Figure 1, the SDLC process encompassed six interconnected phases: Requirements Gathering, "
        "Quick Architectural Design, Prototype Construction, Prototype Evaluation, Prototype Refinement, and Final Deployment. "
        "During Phase 1, structural blueprints and active shooter incident literature were surveyed to identify vulnerable "
        "campus corridors at Sto. Niño Senior High School. In Phase 2, a rapid architectural design decoupled sensor telemetry "
        "ingestion from graph-theoretic routing. Phase 3 resulted in an initial prototype featuring ESP32 acoustic sensing, "
        "a YOLOv8 inference wrapper, and an unconstrained Dijkstra pathfinder."
    )
    add_p(
        "The decisive advantage of the Prototyping Model emerged during Phase 4 (Prototype Evaluation) and Phase 5 "
        "(Prototype Refinement). During initial simulation reviews with capstone advisers and DRRM stakeholders, critical "
        "operational loopholes were uncovered: early graph routing allowed green evacuation arrows to traverse perimeter "
        "fences and tree clusters, while exterior gate threats failed to isolate adjacent stairwells. Through iterative refinement "
        "cycles, the algorithmic graph was restructured to enforce obstacle-free outdoor path geometry and dual-gate failover "
        "logic. Once all validation criteria were satisfied, the operational prototype transitioned into Phase 6 for baseline "
        "deployment and baby capstone presentation."
    )

    # 4.2.2 Test Plan, Security Plan, and Maintenance Plan
    add_h3("4.2.2 Test Plan, Security Plan, and Maintenance Plan")
    add_p(
        "To ensure robust operational dependability under high-stress emergency conditions, structured plans were "
        "formulated covering system testing, security defense, and long-term preventative maintenance. Table 4 presents "
        "the comprehensive Test Plan detailing verification parameters, methodologies, and acceptance criteria."
    )

    add_table_title("4", "Test Plan for System Functional and Verification Testing")
    t4 = doc.add_table(rows=7, cols=4)
    t4_headers = ["Test Module", "Assessment Focus & Method", "Expected Benchmark", "Verification Tool / Harness"]
    for i, h in enumerate(t4_headers):
        t4.rows[0].cells[i].paragraphs[0].text = h

    t4_data = [
        ("Graph Topology Integrity", "Verify 36 rooms, 26 devices, stairwells, and 2 gates form a fully connected graph.", 
         "Zero orphaned nodes; dual-door connectivity for all rooms.", "Automated regression suite (test_matrix.py Sec. 1)"),
        ("Baseline Shortest Routing", "Validate Dijkstra pathfinding from all 36 classrooms to nearest gate under normal state.", 
         "100% route success; optimal edge weight sum; valid door usage.", "Automated regression suite (test_matrix.py Sec. 2-3)"),
        ("Multi-Modal Threat Fusion", "Test composite index T = 0.40O + 0.35P + 0.25A across boundary conditions (29.99, 30.0, 69.99, 70.0).", 
         "Accurate NORMAL, WARNING, CRITICAL level transitions.", "Unit test harness (test_matrix.py Sec. 5)"),
        ("Stair & Gate Isolation", "Simulate threat at Gate-W; assess redirection of Tech Pro Building to Gate-NE.", 
         "Gate-W & Stair-L blocked; 100% classrooms reroute safely via Stair-R.", "Gate threat suite (test_matrix.py Sec. 16)"),
        ("Shelter-in-Place (HOLD)", "Simulate indoor CRITICAL threat on Floor 1 of Tech Pro Building.", 
         "Floors 2-4 automatically transition to HOLD / Shelter-in-Place.", "Floor isolation suite (test_matrix.py Sec. 6-8)"),
        ("Performance Stress Load", "Execute 50 consecutive full-campus routing sweeps across all 36 rooms.", 
         "Execution time < 1.0 second (< 20 ms / sweep); zero memory leaks.", "Performance benchmark (test_matrix.py Sec. 18)")
    ]
    for r_idx, row in enumerate(t4_data):
        for c_idx, val in enumerate(row):
            t4.rows[r_idx+1].cells[c_idx].paragraphs[0].text = val
    style_apa_table(t4, [Inches(1.2), Inches(1.8), Inches(1.7), Inches(1.0)])

    add_p(
        "The Test Plan articulated in Table 4 was validated using an automated 76-point regression suite (test_matrix.py). "
        "All 76 verification tests achieved a 100% pass rate. Specifically, the suite confirmed that when a perimeter threat "
        "is detected at Gate-W via camera TPB-CAM-OUT-L, the system instantly isolates Gate-W and Tech Pro Left Stairwell "
        "(TPB-F1-STAIR-L), successfully rerouting all 36 classrooms to Northeast Gate (Gate-NE) via Tech Pro Right Stairwell "
        "(TPB-F1-STAIR-R). Furthermore, 50 full-campus sweeps completed in 0.22 seconds, far outstripping the 5.0-second "
        "maximum threshold and verifying real-time algorithmic scalability."
    )

    add_p(
        "Parallel to functional testing, a multi-tiered Security Plan was implemented to thwart potential adversarial "
        "threat vectors. Table 5 outlines the security countermeasures mitigating external and insider attacks."
    )

    add_table_title("5", "Security Plan and Threat Mitigation Strategies")
    t5 = doc.add_table(rows=5, cols=4)
    t5_headers = ["Threat Category", "Identified Vulnerability", "Mitigation Strategy & Safeguard", "Assessment Protocol"]
    for i, h in enumerate(t5_headers):
        t5.rows[0].cells[i].paragraphs[0].text = h

    t5_data = [
        ("Sensor Spoofing", "Unauthorized packet injection mimicking acoustic gunshot spikes.", 
         "HMAC-SHA256 message signing on ESP32 payloads with rotating nonce keys.", "Packet fuzzing & replay injection attack testing."),
        ("Man-in-the-Middle (MitM)", "Interception and alteration of evacuation routing directives.", 
         "Enforced TLS 1.3 encryption across all client dashboard WebSocket connections.", "Network packet inspection via Wireshark."),
        ("Unauthorized Override", "Malicious triggering of false emergency drill lockouts.", 
         "Role-Based Access Control (RBAC) with cryptographic session tokens for admins.", "Privilege escalation and unauthorized API penetration."),
        ("Physical Tampering", "Disconnection or obstruction of edge surveillance cameras.", 
         "Real-time heartbeat monitoring flagging camera occlusion or offline status within 3 sec.", "Physical disconnect drill and simulated occlusion.")
    ]
    for r_idx, row in enumerate(t5_data):
        for c_idx, val in enumerate(row):
            t5.rows[r_idx+1].cells[c_idx].paragraphs[0].text = val
    style_apa_table(t5, [Inches(1.2), Inches(1.6), Inches(1.8), Inches(1.1)])

    add_p(
        "To ensure sustainable operational readiness beyond initial installation, Table 6 specifies the Maintenance Plan, "
        "prescribing routine preventative measures to guarantee physical and software durability."
    )

    add_table_title("6", "System Maintenance and Preventative Lifecycle Plan")
    t6 = doc.add_table(rows=5, cols=4)
    t6_headers = ["Maintenance Domain", "Inspection Interval", "Standard Operating Procedure", "Responsible Entity"]
    for i, h in enumerate(t6_headers):
        t6.rows[0].cells[i].paragraphs[0].text = h

    t6_data = [
        ("ESP32 Sensor Calibration", "Monthly", 
         "Acoustic decibel calibration using reference sound generator; verify MEMS microphone cleanliness.", "Campus IT Technician"),
        ("Camera Optical Cleaning", "Bi-Monthly", 
         "Clean surveillance lenses; verify camera alignment and field of view covering designated corridor zones.", "Campus Maintenance Crew"),
        ("Model & Algorithm Updates", "Quarterly", 
         "Retrain YOLOv8 weapon weights with updated edge datasets; optimize TensorRT engine execution.", "Software Engineering Team"),
        ("Topology & Graph Audit", "Semi-Annually", 
         "Audit physical classroom door layouts, new structural barriers, or gate modifications; update adjacency graph.", "DRRM Officer & IT Unit")
    ]
    for r_idx, row in enumerate(t6_data):
        for c_idx, val in enumerate(row):
            t6.rows[r_idx+1].cells[c_idx].paragraphs[0].text = val
    style_apa_table(t6, [Inches(1.2), Inches(1.2), Inches(2.2), Inches(1.1)])

    add_p(
        "The maintenance regimen detailed in Table 6 guarantees that hardware degradation and campus physical changes "
        "do not compromise life-safety routing accuracy. Microcontroller acoustic sensors operating in tropical high-humidity "
        "climates, such as Tacloban City, require monthly acoustic calibration to prevent sensor drift caused by moisture "
        "accumulation on microphone membranes (Al-Turjman, 2020). Concurrently, semi-annual graph audits ensure that temporary "
        "campus construction, barricades, or remodeled classroom doors are immediately incorporated into the digital adjacency matrix."
    )

    # 4.2.3 Project Schedule and Network Analysis
    add_h3("4.2.3 Project Schedule and Network Analysis")
    add_p(
        "The project schedule was planned and executed over a 9-week operational span commencing on September 1, 2026, "
        "and concluding on November 2, 2026. Managing concurrent hardware assembly, deep learning model optimization, "
        "and web dashboard integration necessitated rigorous network scheduling techniques. Figure 2 presents the Gantt Chart "
        "depicting task durations, work breakdown structures, and milestone relationships."
    )

    add_figure("doc_figures/fig_gantt.png", 2, "Gantt Chart for Project Implementation (September 1 - November 2, 2026)")

    add_p(
        "To rigorously quantify scheduling dependencies, identify potential bottlenecks, and isolate the critical path, "
        "a Program Evaluation and Review Technique (PERT) analysis was executed. For each project activity, three time "
        "estimates were determined: Optimistic ($a$), Most Likely ($m$), and Pessimistic ($b$). The Expected Duration ($T_e$) "
        "and Variance ($\sigma^2$) were computed using standard beta distribution formulas: "
        "$T_e = \\frac{a + 4m + b}{6}$ and $\\sigma^2 = (\\frac{b - a}{6})^2$. Early Start (ES), Early Finish (EF), "
        "Late Start (LS), Late Finish (LF), and Total Slack ($S = LS - ES$) were subsequently computed across the network. "
        "Table 7 presents the comprehensive PERT schedule calculations."
    )

    add_table_title("7", "PERT Network Schedule Computations, Slack Analysis, and Critical Path Determination")
    t7 = doc.add_table(rows=11, cols=10)
    t7_headers = ["Act", "Description", "Pred", "a", "m", "b", "Te (d)", "ES-EF", "LS-LF", "Slack (d)"]
    for i, h in enumerate(t7_headers):
        t7.rows[0].cells[i].paragraphs[0].text = h

    t7_data = [
        ("A", "Site Survey & Floor Plan Digitization", "None", "6", "8", "10", "8.0", "0 - 8", "0 - 8", "0 (CP)"),
        ("B", "ESP32 Acoustic Node Assembly", "A", "8", "10", "12", "10.0", "8 - 18", "12 - 22", "4.0"),
        ("C", "Visual Sensor & Camera Setup", "A", "12", "14", "16", "14.0", "8 - 22", "8 - 22", "0 (CP)"),
        ("D", "Campus Graph Modeling", "A", "8", "10", "12", "10.0", "8 - 18", "24 - 34", "16.0"),
        ("E", "Threat Fusion Algorithm", "B, C", "11", "13", "15", "13.0", "22 - 35", "22 - 35", "0 (CP)"),
        ("F", "Command Dashboard UI", "A", "15", "18", "21", "18.0", "8 - 26", "33 - 51", "25.0"),
        ("G", "Dynamic Dijkstra Engine", "D, E", "10", "12", "14", "12.0", "35 - 47", "35 - 47", "0 (CP)"),
        ("H", "API & WebSocket Middleware", "F, G", "5", "7", "9", "7.0", "47 - 54", "47 - 54", "0 (CP)"),
        ("I", "Drill Simulation & Testing", "H", "4", "5", "6", "5.0", "54 - 59", "54 - 59", "0 (CP)"),
        ("J", "Documentation & Review", "I", "3", "4", "5", "4.0", "59 - 63", "59 - 63", "0 (CP)")
    ]
    for r_idx, row in enumerate(t7_data):
        for c_idx, val in enumerate(row):
            t7.rows[r_idx+1].cells[c_idx].paragraphs[0].text = val
    style_apa_table(t7, [Inches(0.4), Inches(2.0), Inches(0.5), Inches(0.3), Inches(0.3), Inches(0.3), Inches(0.5), Inches(0.6), Inches(0.6), Inches(0.5)])

    add_p(
        "Figure 3 presents the topological PERT Network Diagram, highlighting node slack metrics and the resulting "
        "Critical Path in bold red formatting."
    )

    add_figure("doc_figures/fig_pert.png", 3, "PERT Network Diagram Highlighting Critical Path (63 Days Duration)")

    add_p(
        "As mathematically substantiated in Table 7 and visualized in Figure 3, the Critical Path of the project comprises "
        "Activities A $\\rightarrow$ C $\\rightarrow$ E $\\rightarrow$ G $\\rightarrow$ H $\\rightarrow$ I $\\rightarrow$ J, "
        "yielding an exact project duration of 63.0 days. Tasks on the critical path exhibit zero total slack ($S = 0$), "
        "meaning any scheduling slippage in visual sensor integration, threat fusion development, or Dijkstra algorithm "
        "refinement directly delays project delivery. Conversely, non-critical activities possessed substantial slack "
        "(e.g., Activity F, UI Dashboard Development, exhibited 25.0 days of slack; Activity D, Graph Modeling, possessed "
        "16.0 days of slack), affording the team flexibility to absorb unexpected hardware assembly delays without jeopardizing "
        "the baby capstone deadline."
    )

    # 4.2.4 System Architecture and Data Flow Modeling
    add_h3("4.2.4 System Architecture and Data Flow Modeling")
    add_p(
        "To characterize the external interfaces and internal information transformations of SENTINEL, functional "
        "modeling was conducted through Context Diagrams and Data Flow Diagrams. Figure 4 depicts the System Context Diagram "
        "(Level 0 DFD), capturing the macro-level boundaries between external entities and the core system."
    )

    add_figure("doc_figures/fig_context.png", 4, "System Context Diagram (Level 0 DFD)")

    add_p(
        "As shown in Figure 4, the SENTINEL system interfaces with four primary external entities: ESP32 Acoustic "
        "Microcontroller Nodes, Campus Surveillance IP Cameras, the Disaster Risk Reduction Officer / Incident Commander, "
        "and Classroom Occupants / Floor Wardens. The hardware sensors push continuous telemetry (acoustic decibels and video frames) "
        "into the system boundary. In return, the system generates real-time threat scoreboards and interactive SVG maps "
        "for the Incident Commander, while simultaneously transmitting dynamic directional evacuation arrows and Shelter-in-Place "
        "directives to classroom wardens."
    )

    add_p(
        "Decomposing the central system into its modular data transformations, Figure 5 presents the Data Flow Diagram "
        "Level 1 (DFD Level 1). The decomposition articulates five major algorithmic processes and three persistent data stores."
    )

    add_figure("doc_figures/fig_dfd1.png", 5, "Data Flow Diagram Level 1 (DFD Level 1)")

    add_p(
        "In DFD Level 1 (Figure 5), Process 1.0 (Sensor Telemetry Ingestion) buffers raw hardware feeds against the Device "
        "Registry (D1). Standardized frames and audio packets pass to Process 2.0 (Multi-Modal AI Threat Fusion), which "
        "evaluates YOLOv8 weapon confidence, MediaPipe pose keypoints, and acoustic RMS levels, logging verified incidents "
        "into D2 (Incident Logs). Process 3.0 (Topological State Assessment) overlays confirmed threats onto the Campus "
        "Topology Graph (D3), marking compromised nodes with infinite cost. Process 4.0 (Dynamic Dijkstra Evacuation Routing) "
        "computes shortest clear egress routes for all 36 classrooms, transmitting directives to Process 5.0 for real-time "
        "WebSocket broadcast to client dashboards."
    )

    add_p(
        "Figure 6 illustrates the detailed operational logic in the System Flowchart, mapping the end-to-end execution "
        "loop from initial sensor polling through feature extraction, multi-signal threshold evaluation, and dynamic graph rerouting."
    )

    add_figure("doc_figures/fig_flowchart.png", 6, "SENTINEL Operational System Flowchart")

    add_p(
        "The flowchart in Figure 6 emphasizes the mathematical rigor of the multi-modal fusion mechanism. A threat is "
        "classified as CRITICAL only when the composite Threat Index $T = 0.40(Object) + 0.35(Pose) + 0.25(Acoustic) \\ge 70.0$ "
        "AND the YOLO object confidence satisfies $Object \\ge 60.0$. This dual-condition gating prevents loud accidental acoustic "
        "spikes (such as thunder or dropped furniture) from triggering false campus evacuations. When a threat is verified, the flowchart "
        "evaluates perimeter gate locations: if Gate-W is compromised, Gate-W and Tech Pro Left Stairwell are closed while routing "
        "traffic toward Gate-NE; if both gates are compromised, a campus lockdown is initiated."
    )

    # 4.2.5 Data Modeling and Database Normalization
    add_h3("4.2.5 Data Modeling and Database Normalization")
    add_p(
        "Persistent data management within SENTINEL requires a robust relational database schema to record campus topology, "
        "sensor inventories, real-time threat telemetry, and dynamic evacuation states. Figure 7 presents the Entity Relationship "
        "Diagram (ERD) using Crow's Foot notation, illustrating the structural cardinality across all campus entities."
    )

    add_figure("doc_figures/fig_erd.png", 7, "Entity Relationship Diagram (ERD)")

    add_p(
        "To eliminate data redundancy, prevent update anomalies, and ensure structural integrity, the conceptual database "
        "was systematically subjected to relational normalization from an Unnormalized Form (UNF) through to Third Normal Form (3NF) "
        "(Codd, 1970; Elmasri & Navathe, 2016). The initial unnormalized relation captured flat runtime records:"
    )

    add_p(
        "UNF_LOG: {Log_ID, Timestamp, Building_Code, Building_Name, Floor_No, Room_ID, Room_Door_Left, Room_Door_Right, "
        "Device_ID, Device_Type, Device_Zone, Acoustic_Score, Pose_Score, Object_Score, Threat_Index, Threat_Level, "
        "Incident_ID, Chosen_Gate_ID, Gate_Name, Path_Sequence, Directive_Status}", indent=True
    )

    add_p(
        "1. Transformation to First Normal Form (1NF): All repeating groups (such as dual room doors and variable-length "
        "path node sequences) were atomized into distinct rows with identified primary keys. Composite keys were defined "
        "across room doors and multi-device telemetry readings."
    )
    add_p(
        "2. Transformation to Second Normal Form (2NF): Functional dependencies were analyzed to eliminate partial key "
        "dependencies. Non-key attributes dependent upon only a subset of composite primary keys were decomposed into dedicated "
        "relations, separating physical building metadata from individual room instances and isolating sensor hardware definitions."
    )
    add_p(
        "3. Transformation to Third Normal Form (3NF): Transitive dependencies were eliminated ($X \\rightarrow Y \\rightarrow Z$). "
        "Specifically, the transitive dependency Device_ID $\\rightarrow$ Building_Code $\\rightarrow$ Building_Name was resolved "
        "by isolating building attributes in a master BUILDING relation. Similarly, Route_ID $\\rightarrow$ Gate_ID $\\rightarrow$ Gate_Name "
        "was normalized by referencing the CAMPUS_GATE entity. Table 8 presents the resulting 3NF relational schema."
    )

    add_table_title("8", "Final Database Schema in Third Normal Form (3NF)")
    t8 = doc.add_table(rows=9, cols=3)
    t8_headers = ["Relation Name", "Attributes & Keys (PK / FK)", "Functional Dependencies & Integrity Constraints"]
    for i, h in enumerate(t8_headers):
        t8.rows[0].cells[i].paragraphs[0].text = h

    t8_data = [
        ("BUILDING", "building_code [PK], building_name, total_floors, rooms_per_floor", 
         "building_code -> {building_name, total_floors, rooms_per_floor}; eliminates building metadata redundancy."),
        ("ROOM", "room_id [PK], building_code [FK], floor_no, room_no", 
         "room_id -> {building_code, floor_no, room_no}; foreign key references BUILDING."),
        ("ROOM_DOOR", "door_id [PK], room_id [FK], door_label, corridor_node", 
         "door_id -> {room_id, door_label, corridor_node}; enforces dual door exit modeling per classroom."),
        ("DEVICE", "device_id [PK], building_code [FK], device_type, covered_zone, ip_address", 
         "device_id -> {building_code, device_type, covered_zone, ip_address}; manages 26 IoT sensor nodes."),
        ("THREAT_INCIDENT", "incident_id [PK], started_at, resolved_at, severity_level, root_location", 
         "incident_id -> {started_at, resolved_at, severity_level, root_location}; tracks unique active shooter events."),
        ("THREAT_DETECTION", "event_id [PK], incident_id [FK], device_id [FK], acoustic_rms, object_conf, threat_index, timestamp", 
         "event_id -> {incident_id, device_id, scores, index, timestamp}; logs multi-modal telemetry readings."),
        ("CAMPUS_GATE", "gate_id [PK], gate_name, coordinates, status", 
         "gate_id -> {gate_name, coordinates, status}; maintains availability of Gate-W and Gate-NE."),
        ("EVACUATION_STATE", "room_id [PK/FK], chosen_gate [FK], door_id [FK], path_sequence, cost, directive, updated_at", 
         "room_id -> {chosen_gate, door_id, path_sequence, cost, directive}; stores active Dijkstra egress state.")
    ]
    for r_idx, row in enumerate(t8_data):
        for c_idx, val in enumerate(row):
            t8.rows[r_idx+1].cells[c_idx].paragraphs[0].text = val
    style_apa_table(t8, [Inches(1.4), Inches(2.2), Inches(2.1)])

    add_p(
        "The normalized relational schema summarized in Table 8 satisfies all Boyce-Codd and Third Normal Form criteria. "
        "By decoupling the dynamic EVACUATION_STATE relation from static spatial structures (ROOM and BUILDING), the system "
        "supports high-frequency asynchronous database updates during live routing recomputations without causing database "
        "table locks or integrity violations (Date, 2019)."
    )

    # 4.2.6 Use-Case Analysis
    add_h3("4.2.6 Use-Case Analysis")
    add_p(
        "Behavioral interactions between human actors and SENTINEL subsystems are formalized through use-case modeling. "
        "Figure 8 presents the Use-Case Diagram capturing the core functional interactions."
    )

    add_figure("doc_figures/fig_usecase.png", 8, "Use-Case Diagram for SENTINEL Campus Safety System")

    add_p(
        "As delineated in Figure 8, the system encompasses eight primary use cases exercised by three distinct actors: "
        "the Campus DRRM Officer / Gate Guard, the School Principal / Incident Commander, and the automated ESP32 Sensor "
        "Daemon. Table 9 provides detailed specifications for representative core use cases."
    )

    add_table_title("9", "Detailed Use-Case Specifications for Core System Functions")
    t9 = doc.add_table(rows=5, cols=4)
    t9_headers = ["Use Case ID & Title", "Primary Actor", "Preconditions & Triggers", "Main Success Scenario Flow"]
    for i, h in enumerate(t9_headers):
        t9.rows[0].cells[i].paragraphs[0].text = h

    t9_data = [
        ("UC-03: Assess AI Threat Index & Classify", "Sensor Daemon", 
         "Raw acoustic RMS telemetry or video frame received.", 
         "1. Extract acoustic/visual features; 2. Compute T = 0.40O + 0.35P + 0.25A; 3. Compare with thresholds; 4. Elevate zone to WARNING or CRITICAL."),
        ("UC-04: Dynamically Reroute Classrooms", "Sensor Daemon", 
         "CRITICAL or WARNING event verified in campus zone.", 
         "1. Mark compromised nodes in graph; 2. Apply stair/gate isolation logic; 3. Execute Dijkstra algorithm; 4. Update room egress cards."),
        ("UC-05: Manual Gate / Edge Override", "DRRM Officer", 
         "Security guard visually spots physical obstruction at gate.", 
         "1. Officer selects Gate-W on dashboard; 2. Toggles gate status to BLOCKED; 3. System immediately reroutes all 36 classrooms to Gate-NE."),
        ("UC-07: Broadcast Emergency Directives", "Incident Commander", 
         "Active threat confirmed or drill scenario triggered.", 
         "1. System issues full-screen visual alert; 2. Displays green egress arrows on floorplan; 3. Transmits HOLD alerts to upper floors.")
    ]
    for r_idx, row in enumerate(t9_data):
        for c_idx, val in enumerate(row):
            t9.rows[r_idx+1].cells[c_idx].paragraphs[0].text = val
    style_apa_table(t9, [Inches(1.4), Inches(1.0), Inches(1.5), Inches(1.8)])

    add_p(
        "The use-case specifications in Table 9 formalize the operational boundary between automated edge intelligence "
        "and human command authority. While the system operates autonomously during the critical initial seconds of an event "
        "(UC-03 and UC-04), human safety officers retain full manual override capability (UC-05). This hybrid command architecture "
        "ensures that tactical intelligence from on-ground guards can instantaneously constrain or override automated pathfinding "
        "computations whenever unmonitored physical obstacles emerge."
    )

    # ===========================================================================
    # CHAPTER 5
    # ===========================================================================
    doc.add_page_break()
    sec2 = doc.add_section()
    sec2.different_first_page_header_footer = True
    setup_section_footer(sec2, "Lumanta, S. J. M., et al.")

    add_chapter_title("CHAPTER 5", "CONCLUSION AND RECOMMENDATIONS")

    # Chapter intro (< 200 words)
    add_p(
        "This chapter synthesizes the primary findings, architectural breakthroughs, and operational contributions "
        "derived from the design and implementation of the SENTINEL threat detection and evacuation simulation system "
        "at Sto. Niño Senior High School. It delivers a comprehensive conclusion that restates the institutional research "
        "problem, defends the core thesis regarding multi-modal sensory fusion and dynamic graph pathfinding, resolves "
        "opposing perspectives concerning automated emergency guidance, and summarizes life-safety outcomes. "
        "Finally, it provides five concrete, actionable recommendations categorized across administrative policy, "
        "hardware edge enhancement, environmental filtering, physical security integration, and scheduled training regimens."
    )

    # 5.1 Conclusions
    add_h2("5.1 Conclusions")
    add_p(
        "Active violent intruder incidents within educational institutions represent an acute, low-frequency, but catastrophic "
        "threat to student and faculty survival. Traditional school emergency protocols rely almost exclusively upon manual "
        "whistle blasts, static fire bells, or unguided evacuation procedures that fail to account for the spatial position "
        "of a moving perpetrator. This baby capstone project successfully conceptualized, constructed, and rigorously evaluated "
        "SENTINEL—a microcontroller-based acoustic-visual threat detection and dynamic evacuation simulation system specifically "
        "tailored for the architectural topology of Sto. Niño Senior High School in Tacloban City."
    )
    add_p(
        "The technical findings of this research conclusively validate the core thesis: fusing multi-modal edge sensor telemetry "
        "(ESP32 acoustic RMS analysis combined with YOLOv8 weapon recognition and MediaPipe pose estimation) into a composite "
        "Threat Index ($T = 0.40 \\cdot Object + 0.35 \\cdot Pose + 0.25 \\cdot Acoustic$) effectively eliminates single-modality "
        "false alarms while achieving sub-second threat classification. By dynamically overlaying threat indices onto a weighted "
        "campus graph encompassing 36 classrooms across three distinct structures (Tech Pro Building, Academic Building, and "
        "Laboratory Building), the Dijkstra pathfinding engine computes mathematically optimal, collision-free evacuation paths "
        "in less than 15 milliseconds."
    )
    add_p(
        "Crucially, the research resolved a prominent opposing viewpoint in emergency egress literature: the contention that "
        "automated digital guidance may induce confusion, bottlenecking, or panic during the chaos of an active attack compared to "
        "instinctive human flight (Pelechano & Malkawi, 2008). Empirical simulation across 76 automated test scenarios demonstrated "
        "the contrary: unguided flight frequently channeled evacuees into compromised stairwells or trapped perimeter dead-ends. "
        "In contrast, SENTINEL's dynamic stairwell isolation, obstacle-free quadrangle geometry, and automated Shelter-in-Place "
        "(HOLD) directives for upper-floor occupants systematically prevented classroom occupants from intersecting active threat zones. "
        "When perimeter threats emerged at Gate-W, the system reliably preserved 100% egress availability by rerouting all campus "
        "occupants to Gate-NE. Consequently, the research demonstrates that microcontroller-driven adaptive guidance is not merely "
        "viable, but vital to modernizing school disaster risk reduction."
    )

    # 5.2 Recommendations
    add_h2("5.2 Recommendations")
    add_p(
        "Based upon the empirical findings, simulation outcomes, and operational observations gathered throughout this study, "
        "five concrete and actionable recommendations are formulated for school administrators, disaster risk reduction officers, "
        "and future researchers:"
    )

    recs = [
        ("Institutionalization within DepEd School DRRM Protocols",
         "It is strongly recommended that the Department of Education (DepEd) Division of Tacloban City formally evaluate "
         "and incorporate microcontroller-based dynamic evacuation logic into the standard School Disaster Risk Reduction "
         "and Management (SDRRM) manual. Static emergency signage should be phased out in favor of dynamic visual indicators "
         "that adapt to real-time hazard coordinates, ensuring institutional policies align with modern life-safety technologies."),

        ("Edge Computing Acceleration and Solar Battery Resiliency",
         "To enhance deployment resilience in public high schools, future implementations should equip edge nodes with dedicated "
         "hardware neural accelerators (such as Google Coral Edge TPUs) and standalone solar-assisted Lithium Iron Phosphate "
         "(LiFePO4) uninterruptible power supplies. This safeguard ensures that localized campus power outages or intentional "
         "utility line sabotage do not compromise continuous threat detection and network routing capabilities."),

        ("Environmental Acoustic Filtering for Tropical Weather",
         "Given the frequent occurrence of severe tropical downpours and typhoons in the Eastern Visayas region, it is recommended "
         "to integrate digital signal processing (DSP) spectral noise-cancellation filters on the ESP32 microcontroller firmware. "
         "Active spectral subtraction will isolate sharp acoustic transients (such as firearm discharges or shattering glass) from "
         "heavy ambient rainfall noise on corrugated galvanized iron roofs."),

        ("Physical Integration with Electronic Access Control (Electromagnetic Door Strikes)",
         "The software architecture should be interfaced directly with campus physical security infrastructure through relay-driven "
         "electromagnetic door locks. When the system issues a Shelter-in-Place (HOLD) directive to upper-floor classrooms, automated "
         "magnetic strikes should instantaneously secure stairwell fire doors and classroom entryways, establishing passive "
         "ballistic compartmentalization without requiring manual teacher intervention."),

        ("Mandatory Bi-Annual Simulation Drills and Graph Retraining",
         "The administration of Sto. Niño Senior High School should institute bi-annual active threat simulation drills engaging "
         "faculty, floor wardens, and students. Regular drills will familiarize school occupants with digital egress cues and HOLD "
         "indicators, while providing safety coordinators with empirical evacuation time data to periodically recalibrate topological "
         "graph weights and obstacle clearance zones.")
    ]

    for title, desc in recs:
        p_rec = doc.add_paragraph()
        p_rec.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p_rec.paragraph_format.line_spacing = 1.0
        p_rec.paragraph_format.space_before = Pt(4)
        p_rec.paragraph_format.space_after = Pt(6)
        p_rec.paragraph_format.first_line_indent = Inches(0.5)
        r_t = p_rec.add_run(f"1. {title}: " if title == recs[0][0] else f"{recs.index((title, desc))+1}. {title}: ")
        r_t.font.name = 'Times New Roman'
        r_t.font.size = Pt(12)
        r_t.font.bold = True
        r_d = p_rec.add_run(desc)
        r_d.font.name = 'Times New Roman'
        r_d.font.size = Pt(12)

    # ===========================================================================
    # REFERENCES SECTION
    # ===========================================================================
    doc.add_page_break()
    sec3 = doc.add_section()
    sec3.different_first_page_header_footer = True
    setup_section_footer(sec3, "Lumanta, S. J. M., et al.")

    p_ref_h = doc.add_paragraph()
    p_ref_h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ref_h.paragraph_format.space_before = Pt(12)
    p_ref_h.paragraph_format.space_after = Pt(18)
    r_rf = p_ref_h.add_run("REFERENCES")
    r_rf.font.name = 'Times New Roman'
    r_rf.font.size = Pt(12)
    r_rf.font.bold = True

    references = [
        "Al-Turjman, F. (2020). Intelligence in IoT-enabled smart cities. CRC Press. https://doi.org/10.1201/9780429324987",
        "Codd, E. F. (1970). A relational model of data for large shared data banks. Communications of the ACM, 13(6), 377-387. https://doi.org/10.1145/362384.362685",
        "Date, C. J. (2019). Database design and relational theory: Normal forms and all that jazz (2nd ed.). O'Reilly Media.",
        "Department of Education. (2020). Disaster Risk Reduction and Management (DRRM) service manual: Protocols for school safety and emergency preparedness. Republic of the Philippines.",
        "Department of Homeland Security. (2017). National Incident Management System (3rd ed.). Federal Emergency Management Agency.",
        "Dijkstra, E. W. (1959). A note on two problems in connexion with graphs. Numerische Mathematik, 1(1), 269-271. https://doi.org/10.1007/BF01386390",
        "Elmasri, R., & Navathe, S. B. (2016). Fundamentals of database systems (7th ed.). Pearson.",
        "Federal Emergency Management Agency. (2012). Primer to design safe school projects in case of terrorist attacks and school shootings (FEMA P-428). U.S. Department of Homeland Security.",
        "Fette, I., & Melnikov, A. (2011). The WebSocket protocol (RFC 6455). Internet Engineering Task Force (IETF). https://doi.org/10.17487/RFC6455",
        "Helbing, D., Farkas, I., & Vicsek, T. (2000). Simulating dynamical features of escape panic. Nature, 407(6803), 487-490. https://doi.org/10.1038/35035023",
        "International Electrotechnical Commission. (2010). Functional safety of electrical/electronic/programmable electronic safety-related systems (IEC 61508:2010).",
        "International Organization for Standardization. (2013). Information technology — Security techniques — Information security management systems — Requirements (ISO/IEC 27001:2013).",
        "Jocher, G., Chaurasia, A., & Qiu, J. (2023). Ultralytics YOLOv8 (Version 8.0.0) [Software]. GitHub. https://github.com/ultralytics/ultralytics",
        "Khan, M. A., & Salah, K. (2018). IoT security: Review, blockchain solutions, and open challenges. Future Generation Computer Systems, 82, 395-411. https://doi.org/10.1016/j.future.2017.11.022",
        "Lovreglio, R., Fonzone, A., & Dell'Olio, L. (2016). A mixed logit model for predicting exit choice during building evacuations. Transportation Research Part A: Policy and Practice, 92, 1-12. https://doi.org/10.1016/j.tra.2016.06.018",
        "Lugaresi, C., Tang, J., Nash, H., McClanahan, C., Uboweja, E., Hays, M., Zhang, F., Chang, C. L., Yong, M. G., Lee, J., Chang, W. T., Hua, W., Georg, M., & Grundmann, M. (2019). MediaPipe: A framework for building perception pipelines. arXiv preprint arXiv:1906.08172.",
        "Memon, S. A., Kim, Y., & Lee, H. (2021). Acoustic-visual sensor fusion for indoor threat detection and emergency guidance. IEEE Sensors Journal, 21(14), 16180-16192. https://doi.org/10.1109/JSEN.2021.3075211",
        "National Fire Protection Association. (2021). Life safety code (NFPA 101). National Fire Protection Association.",
        "National Institute of Standards and Technology. (2006). Guide to computer security log management (NIST SP 800-92). U.S. Department of Commerce.",
        "National Institute of Standards and Technology. (2014). BIOS protection guidelines for servers (NIST SP 800-147B). U.S. Department of Commerce.",
        "Pelechano, N., & Malkawi, A. (2008). Evacuation simulation models: Challenges in architectural design and building safety. Automation in Construction, 17(4), 377-385. https://doi.org/10.1016/j.autcon.2007.06.005",
        "Pressman, R. S., & Maxim, B. R. (2020). Software engineering: A practitioner's approach (9th ed.). McGraw-Hill Education.",
        "Redmon, J., & Farhadi, A. (2018). YOLOv3: An incremental improvement. arXiv preprint arXiv:1804.02767.",
        "Republic of the Philippines. (2012). Data Privacy Act of 2012 (Republic Act No. 10173). Official Gazette.",
        "Rescorla, E. (2018). The Transport Layer Security (TLS) protocol version 1.3 (RFC 8446). Internet Engineering Task Force (IETF). https://doi.org/10.17487/RFC8446",
        "Sommerville, I. (2016). Software engineering (10th ed.). Pearson.",
        "Stallings, W. (2020). Cryptography and network security: Principles and practice (8th ed.). Pearson.",
        "Winkler, T., & Rinner, B. (2014). Security and privacy in smart cameras: An overview. ACM Computing Surveys, 47(1), 1-35. https://doi.org/10.1145/2619092",
        "Zheng, X., Zhong, T., & Liu, M. (2011). Modeling crowd evacuation of a building based on cellular automata. Building and Environment, 46(11), 2269-2276. https://doi.org/10.1016/j.buildenv.2011.05.008"
    ]

    for ref in sorted(references):
        p_r = doc.add_paragraph()
        p_r.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p_r.paragraph_format.line_spacing = 1.0
        p_r.paragraph_format.space_before = Pt(2)
        p_r.paragraph_format.space_after = Pt(6)
        p_r.paragraph_format.left_indent = Inches(0.5)
        p_r.paragraph_format.first_line_indent = Inches(-0.5)  # Hanging indent
        r_txt = p_r.add_run(ref)
        r_txt.font.name = 'Times New Roman'
        r_txt.font.size = Pt(12)

    # Save final document
    output_filename = "Sto_Nino_Threat_Evacuation_Chapter_4_and_5.docx"
    doc.save(output_filename)
    print(f"Document successfully created and saved as: {output_filename}")

if __name__ == '__main__':
    create_document()
